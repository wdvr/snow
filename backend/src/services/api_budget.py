"""Daily call budgets, circuit breakers and resort demand for external weather APIs.

All state lives in one small DynamoDB table (``API_BUDGET_TABLE``, hash key
``pk``, TTL on ``expires_at``):

- ``budget#<provider>#<YYYY-MM-DD>``: calls used today (``calls``) and an
  optional ``tripped_until`` epoch set by a circuit breaker.
- ``demand#<resort_id>``: a resort someone looked at recently (TTL 48h).

The budget is a hard guard: once a provider's daily limit is reached, callers
must skip the provider until the next UTC day. Calls are reserved in blocks to
keep DynamoDB writes low; a block that is not fully used is simply lost, which
only errs on the safe side.
"""

import logging
import os
import threading
import time
from datetime import UTC, datetime, timedelta

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

API_BUDGET_TABLE = os.environ.get("API_BUDGET_TABLE", "")

# Apple WeatherKit includes 500k calls/month; 15k/day keeps a 31-day month
# under it. Each request asks for two data sets and is counted as 2 units in
# case Apple bills per data set.
WEATHERKIT_DAILY_BUDGET = int(os.environ.get("WEATHERKIT_DAILY_BUDGET", "15000"))
WEATHERKIT_UNITS_PER_CALL = 2
OPENMETEO_DAILY_BUDGET = int(os.environ.get("OPENMETEO_DAILY_BUDGET", "30000"))

DEMAND_TTL_HOURS = 48
# Kept ~6 weeks so month-to-date usage can be reported (analytics dashboard)
BUDGET_ITEM_TTL_DAYS = 40
RESERVE_BLOCK = 10


def _today(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m-%d")


def next_utc_midnight(now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return tomorrow.timestamp()


class ApiBudget:
    """Hard daily budget plus circuit breaker for one provider.

    Without a table (local runs, tests without DynamoDB) the budget is kept
    in memory for the lifetime of the object.
    """

    def __init__(
        self,
        provider: str,
        daily_limit: int,
        table_name: str | None = None,
        dynamodb_resource=None,
        block_size: int = RESERVE_BLOCK,
    ):
        self.provider = provider
        self.daily_limit = daily_limit
        # A block never exceeds the limit (the first reservation of the day
        # has no counter to check against)
        self.block_size = max(1, min(block_size, daily_limit))
        table_name = API_BUDGET_TABLE if table_name is None else table_name
        self._table = None
        if table_name:
            resource = dynamodb_resource or boto3.resource("dynamodb")
            self._table = resource.Table(table_name)
        self._lock = threading.Lock()
        self._day = _today()
        self._reserved = 0  # units reserved from the shared counter, unused
        self._local_used = 0  # in-memory mode only
        self._tripped_until = 0.0
        self._exhausted = False
        self.used = 0  # units used by this process (for logs/tests)
        self.denied = 0

    def _key(self) -> dict:
        return {"pk": f"budget#{self.provider}#{self._day}"}

    def _roll_day(self) -> None:
        today = _today()
        if today != self._day:
            self._day = today
            self._reserved = 0
            self._local_used = 0
            self._exhausted = False

    def is_tripped(self) -> bool:
        return time.time() < self._tripped_until

    def trip(self, until_epoch: float, reason: str = "") -> None:
        """Stop calling the provider until ``until_epoch`` (all processes)."""
        with self._lock:
            self._tripped_until = max(self._tripped_until, until_epoch)
        logger.warning(
            f"{self.provider} circuit breaker tripped until "
            f"{datetime.fromtimestamp(until_epoch, UTC).isoformat()}: {reason}"
        )
        if self._table is None:
            return
        try:
            self._table.update_item(
                Key=self._key(),
                UpdateExpression="SET tripped_until = :t, expires_at = :e",
                ExpressionAttributeValues={
                    ":t": int(until_epoch),
                    ":e": int(time.time()) + BUDGET_ITEM_TTL_DAYS * 86400,
                },
            )
        except ClientError as e:
            logger.warning(f"Failed to persist {self.provider} breaker: {e}")

    def _reserve_block(self, units: int) -> bool:
        """Atomically take ``units`` from today's shared counter."""
        try:
            resp = self._table.update_item(
                Key=self._key(),
                UpdateExpression="ADD calls :n SET expires_at = :e",
                ConditionExpression=(
                    "(attribute_not_exists(calls) OR calls <= :max) AND "
                    "(attribute_not_exists(tripped_until) OR tripped_until < :now)"
                ),
                ExpressionAttributeValues={
                    ":n": units,
                    ":max": self.daily_limit - units,
                    ":now": int(time.time()),
                    ":e": int(time.time()) + BUDGET_ITEM_TTL_DAYS * 86400,
                },
                ReturnValues="UPDATED_NEW",
            )
            used = int(resp.get("Attributes", {}).get("calls", 0))
            self._exhausted = used >= self.daily_limit
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != (
                "ConditionalCheckFailedException"
            ):
                logger.warning(f"{self.provider} budget check failed: {e}")
                return False
            self._load_shared_breaker()
            if not self.is_tripped():
                self._exhausted = True
                logger.warning(
                    f"{self.provider} daily budget of {self.daily_limit} reached; "
                    "skipping the provider until the next UTC day"
                )
            return False

    def _load_shared_breaker(self) -> None:
        try:
            item = self._table.get_item(Key=self._key()).get("Item") or {}
            until = float(item.get("tripped_until", 0))
            if until > self._tripped_until:
                self._tripped_until = until
        except ClientError:
            pass

    def try_consume(self, units: int = 1) -> bool:
        """Return True if the caller may make a call costing ``units``."""
        with self._lock:
            self._roll_day()
            if self.is_tripped() or units > self.daily_limit:
                self.denied += 1
                return False
            if self._table is None:
                if self._local_used + units > self.daily_limit:
                    self.denied += 1
                    return False
                self._local_used += units
                self.used += units
                return True
            if self._reserved < units:
                if self._exhausted:
                    self.denied += 1
                    return False
                block = max(units, self.block_size)
                if self._reserve_block(block):
                    self._reserved += block
                # Near the limit a full block no longer fits: take the exact cost
                elif block > units and self._reserve_block(units):
                    self._reserved += units
                else:
                    self.denied += 1
                    return False
            self._reserved -= units
            self.used += units
            return True


def record_demand(resort_id: str, table=None) -> None:
    """Mark a resort as wanted so the scheduler refreshes it hourly."""
    if table is None:
        if not API_BUDGET_TABLE:
            return
        table = boto3.resource("dynamodb").Table(API_BUDGET_TABLE)
    try:
        table.put_item(
            Item={
                "pk": f"demand#{resort_id}",
                "resort_id": resort_id,
                "expires_at": int(time.time()) + DEMAND_TTL_HOURS * 3600,
            }
        )
    except ClientError as e:
        logger.warning(f"Failed to record demand for {resort_id}: {e}")


def get_demand_resort_ids(table=None) -> set[str]:
    """Resorts viewed in the last 48h (expired items are filtered here too,
    since DynamoDB TTL deletion lags)."""
    if table is None:
        if not API_BUDGET_TABLE:
            return set()
        table = boto3.resource("dynamodb").Table(API_BUDGET_TABLE)
    now = int(time.time())
    ids: set[str] = set()
    kwargs = {
        "FilterExpression": "begins_with(pk, :p) AND expires_at > :now",
        "ExpressionAttributeValues": {":p": "demand#", ":now": now},
        "ProjectionExpression": "resort_id",
    }
    try:
        while True:
            resp = table.scan(**kwargs)
            ids.update(
                i["resort_id"] for i in resp.get("Items", []) if "resort_id" in i
            )
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    except ClientError as e:
        logger.warning(f"Failed to read resort demand: {e}")
    return ids

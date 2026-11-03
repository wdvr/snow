"""DynamoDB type conversion utilities.

DynamoDB stores numbers as Decimal types, but Python/Pydantic models use float/int.
This module provides utilities for converting between the two formats.
"""

import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


def decimal_to_python(obj: Any) -> Any:
    """
    Recursively convert DynamoDB Decimal types to Python float/int types.

    DynamoDB stores all numbers as Decimal. This function converts them back to
    appropriate Python types for use with Pydantic models.

    Args:
        obj: Any object that may contain Decimal values

    Returns:
        The object with all Decimal values converted to float or int
    """
    if isinstance(obj, Decimal):
        # Check if it's a whole number
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {key: decimal_to_python(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_python(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(decimal_to_python(item) for item in obj)
    elif isinstance(obj, set):
        return {decimal_to_python(item) for item in obj}
    return obj


def python_to_decimal(obj: Any) -> Any:
    """
    Recursively convert Python float/int types to Decimal for DynamoDB storage.

    DynamoDB requires Decimal types for numbers. This function converts Python
    float and int values to Decimal, preserving reasonable precision.

    Args:
        obj: Any object that may contain float/int values

    Returns:
        The object with float values converted to Decimal
    """
    if isinstance(obj, float):
        # Convert to string first to avoid float precision issues
        # Round to 6 decimal places to avoid excessive precision
        return Decimal(str(round(obj, 6)))
    elif isinstance(obj, int) and not isinstance(obj, bool):
        # Convert int to Decimal (but not bool, which is a subclass of int)
        return Decimal(obj)
    elif isinstance(obj, dict):
        return {key: python_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [python_to_decimal(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(python_to_decimal(item) for item in obj)
    elif isinstance(obj, set):
        return {python_to_decimal(item) for item in obj}
    return obj


def prepare_for_dynamodb(item: dict[str, Any]) -> dict[str, Any]:
    """
    Prepare a Python dictionary for storage in DynamoDB.

    Converts all float/int values to Decimal type and handles nested structures.

    Args:
        item: Dictionary to prepare for DynamoDB

    Returns:
        Dictionary with all numeric values converted to Decimal
    """
    return python_to_decimal(item)


def parse_from_dynamodb(item: dict[str, Any]) -> dict[str, Any]:
    """
    Parse a DynamoDB item to Python-native types.

    Converts all Decimal values to float/int and handles nested structures.

    Args:
        item: Dictionary from DynamoDB scan/get/query

    Returns:
        Dictionary with all Decimal values converted to float/int
    """
    return decimal_to_python(item)


def parse_items_from_dynamodb(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Parse a list of DynamoDB items to Python-native types.

    Args:
        items: List of dictionaries from DynamoDB

    Returns:
        List of dictionaries with all Decimal values converted
    """
    return [parse_from_dynamodb(item) for item in items]


def batch_get_all(
    client,
    table_name: str,
    keys: list[dict[str, Any]],
    max_retries: int = 5,
    base_delay: float = 0.1,
    **request_options: Any,
) -> list[dict[str, Any]]:
    """batch_get_item that retries UnprocessedKeys with exponential backoff.

    DynamoDB may return part of a batch as UnprocessedKeys when throttled;
    ignoring them silently drops items. Chunks keys into groups of 100.
    Items still unprocessed after max_retries are logged and skipped.
    """
    items: list[dict[str, Any]] = []
    for start in range(0, len(keys), 100):
        request = {table_name: {"Keys": keys[start : start + 100], **request_options}}
        attempt = 0
        while request:
            response = client.batch_get_item(RequestItems=request)
            items.extend(response.get("Responses", {}).get(table_name, []))
            request = response.get("UnprocessedKeys") or {}
            if not request:
                break
            if attempt >= max_retries:
                missing = len(request.get(table_name, {}).get("Keys", []))
                logger.warning(
                    f"batch_get_item on {table_name}: giving up on {missing} "
                    f"unprocessed keys after {max_retries} retries"
                )
                break
            time.sleep(base_delay * (2**attempt))
            attempt += 1
    return items

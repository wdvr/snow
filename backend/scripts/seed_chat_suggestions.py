#!/usr/bin/env python3
"""
Seed the chat suggestions DynamoDB table with default suggestions.

Usage:
    python scripts/seed_chat_suggestions.py [--env ENV] [--dry-run]

Options:
    --env ENV    Environment (dev, staging, prod). Default: dev
    --dry-run    Show what would be written without actually writing
"""

import argparse
import logging
import sys
from datetime import UTC, datetime

import boto3

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SUGGESTIONS = [
    # General (no tokens)
    {
        "suggestion_id": "s1",
        "text": "What are the snow conditions like today?",
        "category": "general",
        "priority": 1,
        "active": True,
    },
    {
        "suggestion_id": "s2",
        "text": "Which resort has the most fresh snow?",
        "category": "general",
        "priority": 2,
        "active": True,
    },
    {
        "suggestion_id": "s3",
        "text": "Compare Whistler and Vail conditions",
        "category": "general",
        "priority": 3,
        "active": True,
    },
    {
        "suggestion_id": "s4",
        "text": "What's the snow quality forecast for this week?",
        "category": "general",
        "priority": 4,
        "active": True,
    },
    # Favorites-aware (use {resort_name} token)
    {
        "suggestion_id": "s5",
        "text": "How's the powder at {resort_name} today?",
        "category": "favorites_aware",
        "priority": 5,
        "active": True,
    },
    {
        "suggestion_id": "s7",
        "text": "What's the forecast for {resort_name}?",
        "category": "favorites_aware",
        "priority": 7,
        "active": True,
    },
    {
        "suggestion_id": "s8",
        "text": "Should I go to {resort_name} or {resort_name_2} tomorrow?",
        "category": "favorites_aware",
        "priority": 8,
        "active": True,
    },
    {
        "suggestion_id": "s9",
        "text": "Any fresh snow expected at {resort_name}?",
        "category": "favorites_aware",
        "priority": 9,
        "active": True,
    },
    {
        "suggestion_id": "s10",
        "text": "How deep is the base at {resort_name}?",
        "category": "favorites_aware",
        "priority": 10,
        "active": True,
    },
    {
        "suggestion_id": "s13",
        "text": "Is {resort_name} worth the trip today?",
        "category": "favorites_aware",
        "priority": 13,
        "active": True,
    },
    {
        "suggestion_id": "s14",
        "text": "Will it snow at {resort_name} this week?",
        "category": "favorites_aware",
        "priority": 14,
        "active": True,
    },
    # Location-aware (use {nearby_city} or {region} tokens)
    {
        "suggestion_id": "s6",
        "text": "Best snow near {nearby_city} this weekend?",
        "category": "location_aware",
        "priority": 6,
        "active": True,
    },
    {
        "suggestion_id": "s11",
        "text": "What are conditions like in {region}?",
        "category": "location_aware",
        "priority": 11,
        "active": True,
    },
    {
        "suggestion_id": "s12",
        "text": "Best resort for beginners near {nearby_city}?",
        "category": "location_aware",
        "priority": 12,
        "active": True,
    },
    {
        "suggestion_id": "s15",
        "text": "Hidden gems near {nearby_city} with good powder?",
        "category": "location_aware",
        "priority": 15,
        "active": True,
    },
    {
        "suggestion_id": "s16",
        "text": "How's the weather looking in {region} this weekend?",
        "category": "location_aware",
        "priority": 16,
        "active": True,
    },
]


def seed_suggestions(env: str, dry_run: bool = False):
    """Seed the chat suggestions table."""
    table_name = f"snow-tracker-chat-suggestions-{env}"
    logger.info("Seeding %d suggestions to %s", len(SUGGESTIONS), table_name)

    if dry_run:
        for s in SUGGESTIONS:
            logger.info(
                "  [DRY RUN] %s: %s (%s, priority=%d)",
                s["suggestion_id"],
                s["text"],
                s["category"],
                s["priority"],
            )
        return

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    now = datetime.now(UTC).isoformat()

    with table.batch_writer() as batch:
        for suggestion in SUGGESTIONS:
            item = {**suggestion, "created_at": now}
            batch.put_item(Item=item)
            logger.info(
                "  Written: %s — %s", suggestion["suggestion_id"], suggestion["text"]
            )

    logger.info("Done. %d suggestions seeded to %s.", len(SUGGESTIONS), table_name)


def main():
    parser = argparse.ArgumentParser(description="Seed chat suggestions table")
    parser.add_argument(
        "--env",
        default="dev",
        choices=["dev", "staging", "prod"],
        help="Environment (default: dev)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without actually writing",
    )
    args = parser.parse_args()
    seed_suggestions(args.env, args.dry_run)


if __name__ == "__main__":
    main()

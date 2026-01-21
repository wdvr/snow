"""Utility functions and scripts for Snow Quality Tracker."""

# Import dynamodb_utils first as it has no dependencies on services
from .dynamodb_utils import (
    decimal_to_python,
    parse_from_dynamodb,
    parse_items_from_dynamodb,
    prepare_for_dynamodb,
    python_to_decimal,
)

# Note: ResortSeeder is not imported here to avoid circular import with resort_service.
# Import it directly when needed: from src.utils.resort_seeder import ResortSeeder

__all__ = [
    "decimal_to_python",
    "python_to_decimal",
    "prepare_for_dynamodb",
    "parse_from_dynamodb",
    "parse_items_from_dynamodb",
]


def get_resort_seeder():
    """Lazy import of ResortSeeder to avoid circular dependency."""
    from .resort_seeder import ResortSeeder

    return ResortSeeder

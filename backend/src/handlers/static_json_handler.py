"""Lambda handler for generating static JSON API files.

This handler can be triggered:
1. Directly by the weather processor after sequential processing
2. By a scheduled CloudWatch event (for parallel processing mode)
3. Manually via the Lambda console or CLI

The static JSON files are uploaded to S3 and served via CloudFront for
fast edge-cached responses, reducing DynamoDB costs and improving app performance.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from services.static_json_generator import generate_static_json_api

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def static_json_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Lambda handler to generate static JSON API files.

    This generates:
    - /data/resorts.json - All resort metadata
    - /data/snow-quality.json - All resort snow quality summaries

    Args:
        event: Lambda event (can be CloudWatch scheduled event or direct invocation)
        context: Lambda context

    Returns:
        Dict with generation results
    """
    logger.info(f"Starting static JSON generation at {datetime.now(UTC).isoformat()}")
    logger.info(f"Event: {json.dumps(event)}")

    try:
        result = generate_static_json_api()

        if result.get("success"):
            logger.info(f"Static JSON generation successful: {result}")
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Static JSON API files generated successfully",
                        "result": result,
                    }
                ),
            }
        else:
            logger.warning(f"Static JSON generation completed with errors: {result}")
            return {
                "statusCode": 207,  # Multi-Status
                "body": json.dumps(
                    {
                        "message": "Static JSON API files generated with errors",
                        "result": result,
                    }
                ),
            }

    except Exception as e:
        logger.error(f"Failed to generate static JSON: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "message": "Failed to generate static JSON API files",
                    "error": str(e),
                }
            ),
        }

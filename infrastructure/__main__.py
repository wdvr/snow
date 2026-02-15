"""
Snow Quality Tracker - AWS Infrastructure

This Pulumi program defines the AWS infrastructure for the Snow Quality Tracker app:
- S3 bucket for Pulumi state storage
- DynamoDB tables for data storage
- API Gateway for REST API
- Lambda functions for weather processing
- IAM roles and policies
- CloudWatch for monitoring
- EKS cluster with Grafana/Prometheus (staging/prod only)
"""

import pulumi
import pulumi_aws as aws

from monitoring import create_monitoring_stack, create_api_gateway_monitoring

# Get configuration values
config = pulumi.Config()
app_name = config.get("appName") or "snow-tracker"
environment = config.get("env") or "dev"
aws_config = pulumi.Config("aws")
aws_region = aws_config.get("region") or "us-west-2"

# Get AWS account ID for unique bucket names
caller_identity = aws.get_caller_identity()

# Create tags for all resources
tags = {
    "Project": "Snow Quality Tracker",
    "Environment": environment,
    "ManagedBy": "Pulumi",
}

# S3 Bucket for Pulumi State Storage
# Note: This bucket is shared across all environments for state storage
# Use get_bucket to check if it exists, otherwise create it
state_bucket_name = f"{app_name}-pulumi-state-{aws_region}"

# Try to get existing bucket, create if it doesn't exist
try:
    existing_bucket = aws.s3.get_bucket(bucket=state_bucket_name)
    pulumi_state_bucket = aws.s3.BucketV2.get(
        f"{app_name}-pulumi-state",
        id=state_bucket_name,
    )
    pulumi.log.info(f"Using existing S3 bucket: {state_bucket_name}")
except Exception:
    # Bucket doesn't exist, create it
    pulumi_state_bucket = aws.s3.BucketV2(
        f"{app_name}-pulumi-state",
        bucket=state_bucket_name,
        tags=tags,
    )

    # Enable versioning
    aws.s3.BucketVersioningV2(
        f"{app_name}-pulumi-state-versioning",
        bucket=pulumi_state_bucket.id,
        versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(
            status="Enabled"
        ),
    )

    # Enable server-side encryption
    aws.s3.BucketServerSideEncryptionConfigurationV2(
        f"{app_name}-pulumi-state-encryption",
        bucket=pulumi_state_bucket.id,
        rules=[
            aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm="AES256"
                )
            )
        ],
    )

    # Add lifecycle rules
    aws.s3.BucketLifecycleConfigurationV2(
        f"{app_name}-pulumi-state-lifecycle",
        bucket=pulumi_state_bucket.id,
        rules=[
            aws.s3.BucketLifecycleConfigurationV2RuleArgs(
                id="cleanup-old-versions",
                status="Enabled",
                noncurrent_version_expiration=aws.s3.BucketLifecycleConfigurationV2RuleNoncurrentVersionExpirationArgs(
                    noncurrent_days=90
                ),
            )
        ],
    )

    pulumi.log.info(f"Created new S3 bucket: {state_bucket_name}")

# Block public access on state bucket
pulumi_state_bucket_public_access_block = aws.s3.BucketPublicAccessBlock(
    f"{app_name}-pulumi-state-public-access-block",
    bucket=pulumi_state_bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

# DynamoDB Tables
resorts_table = aws.dynamodb.Table(
    f"{app_name}-resorts-{environment}",
    name=f"{app_name}-resorts-{environment}",
    billing_mode="PAY_PER_REQUEST",
    hash_key="resort_id",
    attributes=[
        {"name": "resort_id", "type": "S"},
        {"name": "country", "type": "S"},
        {"name": "geo_hash", "type": "S"},
    ],
    global_secondary_indexes=[
        {"name": "CountryIndex", "hash_key": "country", "projection_type": "ALL"},
        {"name": "GeoHashIndex", "hash_key": "geo_hash", "projection_type": "ALL"},
    ],
    tags=tags,
)

weather_conditions_table = aws.dynamodb.Table(
    f"{app_name}-weather-conditions-{environment}",
    name=f"{app_name}-weather-conditions-{environment}",
    billing_mode="PAY_PER_REQUEST",
    hash_key="resort_id",
    range_key="timestamp",
    attributes=[
        {"name": "resort_id", "type": "S"},
        {"name": "timestamp", "type": "S"},
        {"name": "elevation_level", "type": "S"},
    ],
    global_secondary_indexes=[
        {
            "name": "ElevationIndex",
            "hash_key": "elevation_level",
            "range_key": "timestamp",
            "projection_type": "ALL",
        }
    ],
    ttl={"attribute_name": "ttl", "enabled": True},
    tags=tags,
)

user_preferences_table = aws.dynamodb.Table(
    f"{app_name}-user-preferences-{environment}",
    name=f"{app_name}-user-preferences-{environment}",
    billing_mode="PAY_PER_REQUEST",
    hash_key="user_id",
    attributes=[{"name": "user_id", "type": "S"}],
    tags=tags,
)

feedback_table = aws.dynamodb.Table(
    f"{app_name}-feedback-{environment}",
    name=f"{app_name}-feedback-{environment}",
    billing_mode="PAY_PER_REQUEST",
    hash_key="feedback_id",
    attributes=[
        {"name": "feedback_id", "type": "S"},
        {"name": "status", "type": "S"},
        {"name": "created_at", "type": "S"},
    ],
    global_secondary_indexes=[
        {
            "name": "StatusIndex",
            "hash_key": "status",
            "range_key": "created_at",
            "projection_type": "ALL",
        }
    ],
    tags=tags,
)

# Device tokens table for push notifications (APNs)
device_tokens_table = aws.dynamodb.Table(
    f"{app_name}-device-tokens-{environment}",
    name=f"{app_name}-device-tokens-{environment}",
    billing_mode="PAY_PER_REQUEST",
    hash_key="user_id",
    range_key="device_id",
    attributes=[
        {"name": "user_id", "type": "S"},
        {"name": "device_id", "type": "S"},
    ],
    ttl={"attribute_name": "ttl", "enabled": True},
    tags=tags,
)

# Snow summary table for persisting accumulated snow data
# This table survives weather conditions TTL expiration
# Stores season-long accumulation and last freeze dates
snow_summary_table = aws.dynamodb.Table(
    f"{app_name}-snow-summary-{environment}",
    name=f"{app_name}-snow-summary-{environment}",
    billing_mode="PAY_PER_REQUEST",
    hash_key="resort_id",
    range_key="elevation_level",  # base, mid, top
    attributes=[
        {"name": "resort_id", "type": "S"},
        {"name": "elevation_level", "type": "S"},
    ],
    # NO TTL - this data persists forever for season-long tracking
    tags=tags,
)

# Resort events table for tracking events at resorts
resort_events_table = aws.dynamodb.Table(
    f"{app_name}-resort-events-{environment}",
    name=f"{app_name}-resort-events-{environment}",
    billing_mode="PAY_PER_REQUEST",
    hash_key="resort_id",
    range_key="event_id",
    attributes=[
        {"name": "resort_id", "type": "S"},
        {"name": "event_id", "type": "S"},
        {"name": "event_date", "type": "S"},
    ],
    global_secondary_indexes=[
        {
            "name": "EventDateIndex",
            "hash_key": "resort_id",
            "range_key": "event_date",
            "projection_type": "ALL",
        }
    ],
    ttl={"attribute_name": "ttl", "enabled": True},
    tags=tags,
)

# IAM Role for Lambda functions
lambda_role = aws.iam.Role(
    f"{app_name}-lambda-role-{environment}",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                }
            }
        ]
    }""",
    tags=tags,
)

# Website bucket name pattern for static JSON API (account_id is a plain string from get_caller_identity)
website_bucket_name = f"{app_name}-website-{environment}-{caller_identity.account_id}"

# IAM Policy for Lambda to access DynamoDB and CloudWatch
lambda_policy = aws.iam.RolePolicy(
    f"{app_name}-lambda-policy-{environment}",
    role=lambda_role.id,
    policy=pulumi.Output.all(
        resorts_table.arn,
        weather_conditions_table.arn,
        user_preferences_table.arn,
        feedback_table.arn,
        device_tokens_table.arn,
        resort_events_table.arn,
        snow_summary_table.arn,
    ).apply(
        lambda arns: f"""{{
        "Version": "2012-10-17",
        "Statement": [
            {{
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:*"
            }},
            {{
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:BatchGetItem"
                ],
                "Resource": [
                    "{arns[0]}",
                    "{arns[1]}",
                    "{arns[2]}",
                    "{arns[3]}",
                    "{arns[4]}",
                    "{arns[5]}",
                    "{arns[6]}",
                    "{arns[0]}/index/*",
                    "{arns[1]}/index/*",
                    "{arns[2]}/index/*",
                    "{arns[3]}/index/*",
                    "{arns[4]}/index/*",
                    "{arns[5]}/index/*",
                    "{arns[6]}/index/*"
                ]
            }},
            {{
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction"
                ],
                "Resource": "arn:aws:lambda:*:*:function:snow-tracker-*"
            }},
            {{
                "Effect": "Allow",
                "Action": [
                    "sns:CreatePlatformEndpoint",
                    "sns:Publish",
                    "sns:GetEndpointAttributes",
                    "sns:SetEndpointAttributes"
                ],
                "Resource": "*"
            }},
            {{
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:ListBucket"
                ],
                "Resource": [
                    "arn:aws:s3:::snow-tracker-pulumi-state-us-west-2",
                    "arn:aws:s3:::snow-tracker-pulumi-state-us-west-2/scraper-results/*",
                    "arn:aws:s3:::snow-tracker-pulumi-state-us-west-2/resort-versions/*",
                    "arn:aws:s3:::{website_bucket_name}",
                    "arn:aws:s3:::{website_bucket_name}/data/*"
                ]
            }},
            {{
                "Effect": "Allow",
                "Action": [
                    "cloudwatch:PutMetricData"
                ],
                "Resource": "*"
            }}
        ]
    }}"""
    ),
)

# CloudWatch Log Group for Lambda functions
log_group = aws.cloudwatch.LogGroup(
    f"{app_name}-lambda-logs-{environment}",
    name=f"/aws/lambda/{app_name}-{environment}",
    retention_in_days=14,
    tags=tags,
)

# Weather processor log group
weather_processor_log_group = aws.cloudwatch.LogGroup(
    f"{app_name}-weather-processor-logs-{environment}",
    name=f"/aws/lambda/{app_name}-weather-processor-{environment}",
    retention_in_days=14,
    tags=tags,
)

# Lambda function for weather data processing
# Note: The actual code package is deployed separately via CI/CD
# Placeholder code that will be replaced by CI/CD
placeholder_lambda_code = """
def handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Placeholder - deploy actual code via CI/CD'
    }
"""

# SNS Topic for new resort notifications (must be defined before Lambdas that use it)
new_resorts_topic = aws.sns.Topic(
    f"{app_name}-new-resorts-{environment}",
    name=f"{app_name}-new-resorts-{environment}",
    tags=tags,
)

# Email subscription for new resort notifications (only in prod)
if environment == "prod":
    new_resorts_email_subscription = aws.sns.TopicSubscription(
        f"{app_name}-new-resorts-email-{environment}",
        topic=new_resorts_topic.arn,
        protocol="email",
        endpoint="wouterdevriendt@gmail.com",
    )

weather_processor_lambda = aws.lambda_.Function(
    f"{app_name}-weather-processor-{environment}",
    name=f"{app_name}-weather-processor-{environment}",
    role=lambda_role.arn,
    handler="handlers.weather_processor.weather_processor_handler",
    runtime="python3.12",
    timeout=600,  # 10 minutes for processing all resorts (scaled for 1000+ resorts)
    memory_size=256,
    code=pulumi.AssetArchive(
        {
            "index.py": pulumi.StringAsset(placeholder_lambda_code),
        }
    ),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "ENVIRONMENT": environment,
            "RESORTS_TABLE": f"{app_name}-resorts-{environment}",
            "WEATHER_CONDITIONS_TABLE": f"{app_name}-weather-conditions-{environment}",
            "AWS_REGION_NAME": aws_region,
            # Parallel processing: enabled by default for 1000+ resort scale
            "PARALLEL_PROCESSING": config.get("parallelWeatherProcessing") or "true",
            "WEATHER_WORKER_LAMBDA": f"{app_name}-weather-worker-{environment}",
            # Static JSON API generation (uploads to website bucket)
            "ENABLE_STATIC_JSON": config.get("enableStaticJson") or "true",
            "WEBSITE_BUCKET": website_bucket_name,
        }
    ),
    tags=tags,
    opts=pulumi.ResourceOptions(depends_on=[lambda_role, weather_processor_log_group]),
)

# Weather worker log group (for parallel processing)
weather_worker_log_group = aws.cloudwatch.LogGroup(
    f"{app_name}-weather-worker-logs-{environment}",
    name=f"/aws/lambda/{app_name}-weather-worker-{environment}",
    retention_in_days=14,
    tags=tags,
)

# Weather worker Lambda (for parallel processing - one per region)
weather_worker_lambda = aws.lambda_.Function(
    f"{app_name}-weather-worker-{environment}",
    name=f"{app_name}-weather-worker-{environment}",
    role=lambda_role.arn,
    handler="handlers.weather_worker.weather_worker_handler",
    runtime="python3.12",
    timeout=600,  # 10 minutes per region batch (scaled for large regions)
    memory_size=256,
    code=pulumi.AssetArchive(
        {
            "index.py": pulumi.StringAsset(placeholder_lambda_code),
        }
    ),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "ENVIRONMENT": environment,
            "RESORTS_TABLE": f"{app_name}-resorts-{environment}",
            "WEATHER_CONDITIONS_TABLE": f"{app_name}-weather-conditions-{environment}",
            "AWS_REGION_NAME": aws_region,
            "ENABLE_SCRAPING": "true",
        }
    ),
    tags=tags,
    opts=pulumi.ResourceOptions(depends_on=[lambda_role, weather_worker_log_group]),
)

# CloudWatch Events rule to trigger weather processor every hour
weather_schedule_rule = aws.cloudwatch.EventRule(
    f"{app_name}-weather-schedule-{environment}",
    name=f"{app_name}-weather-schedule-{environment}",
    description="Trigger weather data fetch every hour",
    schedule_expression="rate(1 hour)",
    tags=tags,
)

# Permission for CloudWatch Events to invoke the Lambda
weather_schedule_permission = aws.lambda_.Permission(
    f"{app_name}-weather-schedule-permission-{environment}",
    action="lambda:InvokeFunction",
    function=weather_processor_lambda.name,
    principal="events.amazonaws.com",
    source_arn=weather_schedule_rule.arn,
)

# CloudWatch Events target to invoke the weather processor Lambda
weather_schedule_target = aws.cloudwatch.EventTarget(
    f"{app_name}-weather-schedule-target-{environment}",
    rule=weather_schedule_rule.name,
    arn=weather_processor_lambda.arn,
)

# =============================================================================
# Static JSON Generator Lambda - Generates pre-computed JSON for edge caching
# =============================================================================

# Static JSON generator log group
static_json_log_group = aws.cloudwatch.LogGroup(
    f"{app_name}-static-json-logs-{environment}",
    name=f"/aws/lambda/{app_name}-static-json-{environment}",
    retention_in_days=14,
    tags=tags,
)

# Static JSON generator Lambda
static_json_lambda = aws.lambda_.Function(
    f"{app_name}-static-json-{environment}",
    name=f"{app_name}-static-json-{environment}",
    role=lambda_role.arn,
    handler="handlers.static_json_handler.static_json_handler",
    runtime="python3.12",
    timeout=300,  # 5 minutes to generate and upload all JSON files
    memory_size=256,
    code=pulumi.AssetArchive(
        {
            "index.py": pulumi.StringAsset(placeholder_lambda_code),
        }
    ),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "ENVIRONMENT": environment,
            "RESORTS_TABLE": f"{app_name}-resorts-{environment}",
            "WEATHER_CONDITIONS_TABLE": f"{app_name}-weather-conditions-{environment}",
            "WEBSITE_BUCKET": website_bucket_name,
            "AWS_REGION_NAME": aws_region,
        }
    ),
    tags=tags,
    opts=pulumi.ResourceOptions(depends_on=[lambda_role, static_json_log_group]),
)

# Schedule static JSON generation 15 minutes after weather processor
# This gives enough time for all parallel workers to complete
static_json_schedule_rule = aws.cloudwatch.EventRule(
    f"{app_name}-static-json-schedule-{environment}",
    name=f"{app_name}-static-json-schedule-{environment}",
    description="Generate static JSON API files 15 minutes after each hour",
    schedule_expression="cron(15 * * * ? *)",  # 15 minutes past every hour
    tags=tags,
)

# Permission for CloudWatch Events to invoke the static JSON Lambda
static_json_schedule_permission = aws.lambda_.Permission(
    f"{app_name}-static-json-schedule-permission-{environment}",
    action="lambda:InvokeFunction",
    function=static_json_lambda.name,
    principal="events.amazonaws.com",
    source_arn=static_json_schedule_rule.arn,
)

# CloudWatch Events target for static JSON generation
static_json_schedule_target = aws.cloudwatch.EventTarget(
    f"{app_name}-static-json-schedule-target-{environment}",
    rule=static_json_schedule_rule.name,
    arn=static_json_lambda.arn,
)

# =============================================================================
# Scraper Lambdas - Parallel resort scraping by country
# =============================================================================

# Scraper orchestrator log group
scraper_orchestrator_log_group = aws.cloudwatch.LogGroup(
    f"{app_name}-scraper-orchestrator-logs-{environment}",
    name=f"/aws/lambda/{app_name}-scraper-orchestrator-{environment}",
    retention_in_days=14,
    tags=tags,
)

# Scraper orchestrator Lambda
scraper_orchestrator_lambda = aws.lambda_.Function(
    f"{app_name}-scraper-orchestrator-{environment}",
    name=f"{app_name}-scraper-orchestrator-{environment}",
    role=lambda_role.arn,
    handler="handlers.scraper_orchestrator.scraper_orchestrator_handler",
    runtime="python3.12",
    timeout=60,  # Orchestrator just dispatches, doesn't do heavy work
    memory_size=256,
    code=pulumi.AssetArchive(
        {
            "index.py": pulumi.StringAsset(placeholder_lambda_code),
        }
    ),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "ENVIRONMENT": environment,
            "SCRAPER_WORKER_LAMBDA": f"{app_name}-scraper-worker-{environment}",
            "RESULTS_BUCKET": state_bucket_name,
            "RESORTS_TABLE": f"{app_name}-resorts-{environment}",
            "AWS_REGION_NAME": aws_region,
        }
    ),
    tags=tags,
    opts=pulumi.ResourceOptions(
        depends_on=[lambda_role, scraper_orchestrator_log_group]
    ),
)

# Scraper worker log group
scraper_worker_log_group = aws.cloudwatch.LogGroup(
    f"{app_name}-scraper-worker-logs-{environment}",
    name=f"/aws/lambda/{app_name}-scraper-worker-{environment}",
    retention_in_days=14,
    tags=tags,
)

# Scraper worker Lambda (processes one country)
scraper_worker_lambda = aws.lambda_.Function(
    f"{app_name}-scraper-worker-{environment}",
    name=f"{app_name}-scraper-worker-{environment}",
    role=lambda_role.arn,
    handler="handlers.scraper_worker.scraper_worker_handler",
    runtime="python3.12",
    timeout=600,  # 10 minutes per country (some countries have many resorts)
    memory_size=512,  # More memory for HTML parsing
    code=pulumi.AssetArchive(
        {
            "index.py": pulumi.StringAsset(placeholder_lambda_code),
        }
    ),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "ENVIRONMENT": environment,
            "RESULTS_BUCKET": state_bucket_name,
            "RESORTS_TABLE": f"{app_name}-resorts-{environment}",
            "AWS_REGION_NAME": aws_region,
            "NEW_RESORTS_TOPIC_ARN": new_resorts_topic.arn,
        }
    ),
    tags=tags,
    opts=pulumi.ResourceOptions(
        depends_on=[lambda_role, scraper_worker_log_group, new_resorts_topic]
    ),
)

# Daily scraper schedule (06:00 UTC - delta mode by default, full on 1st of month)
scraper_schedule_rule = aws.cloudwatch.EventRule(
    f"{app_name}-scraper-schedule-{environment}",
    name=f"{app_name}-scraper-schedule-{environment}",
    description="Trigger resort scraping daily at 06:00 UTC",
    schedule_expression="cron(0 6 * * ? *)",
    tags=tags,
)

# Permission for CloudWatch Events to invoke the scraper orchestrator
scraper_schedule_permission = aws.lambda_.Permission(
    f"{app_name}-scraper-schedule-permission-{environment}",
    action="lambda:InvokeFunction",
    function=scraper_orchestrator_lambda.name,
    principal="events.amazonaws.com",
    source_arn=scraper_schedule_rule.arn,
)

# CloudWatch Events target for scraper
scraper_schedule_target = aws.cloudwatch.EventTarget(
    f"{app_name}-scraper-schedule-target-{environment}",
    rule=scraper_schedule_rule.name,
    arn=scraper_orchestrator_lambda.arn,
)

# =============================================================================
# Scraper Results Processor Lambda - Processes S3 results into DynamoDB
# =============================================================================

# Log group for scraper results processor
scraper_results_processor_log_group = aws.cloudwatch.LogGroup(
    f"{app_name}-scraper-results-processor-logs-{environment}",
    name=f"/aws/lambda/{app_name}-scraper-results-processor-{environment}",
    retention_in_days=14,
    tags=tags,
)

# Scraper results processor Lambda
scraper_results_processor_lambda = aws.lambda_.Function(
    f"{app_name}-scraper-results-processor-{environment}",
    name=f"{app_name}-scraper-results-processor-{environment}",
    role=lambda_role.arn,
    handler="handlers.scraper_orchestrator.process_scraper_results_handler",
    runtime="python3.12",
    timeout=300,  # 5 minutes to process results
    memory_size=256,
    code=pulumi.AssetArchive(
        {
            "index.py": pulumi.StringAsset(placeholder_lambda_code),
        }
    ),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "ENVIRONMENT": environment,
            "RESULTS_BUCKET": state_bucket_name,
            "RESORTS_TABLE": f"{app_name}-resorts-{environment}",
            "AWS_REGION_NAME": aws_region,
        }
    ),
    tags=tags,
    opts=pulumi.ResourceOptions(
        depends_on=[lambda_role, scraper_results_processor_log_group]
    ),
)

# Schedule to process results 1 hour after scraper (07:00 UTC) - staging only
# Prod requires manual approval
if environment == "staging":
    scraper_results_schedule_rule = aws.cloudwatch.EventRule(
        f"{app_name}-scraper-results-schedule-{environment}",
        name=f"{app_name}-scraper-results-schedule-{environment}",
        description="Process scraper results daily at 07:00 UTC (1 hour after scraper)",
        schedule_expression="cron(0 7 * * ? *)",
        tags=tags,
    )

    scraper_results_schedule_permission = aws.lambda_.Permission(
        f"{app_name}-scraper-results-schedule-permission-{environment}",
        action="lambda:InvokeFunction",
        function=scraper_results_processor_lambda.name,
        principal="events.amazonaws.com",
        source_arn=scraper_results_schedule_rule.arn,
    )

    # Pass yesterday's job_id pattern to process
    scraper_results_schedule_target = aws.cloudwatch.EventTarget(
        f"{app_name}-scraper-results-schedule-target-{environment}",
        rule=scraper_results_schedule_rule.name,
        arn=scraper_results_processor_lambda.arn,
        input='{"process_latest": true}',
    )

# =============================================================================
# Version Consolidator Lambda - Aggregates scraper results into versioned snapshots
# =============================================================================

# Log group for version consolidator
version_consolidator_log_group = aws.cloudwatch.LogGroup(
    f"{app_name}-version-consolidator-logs-{environment}",
    name=f"/aws/lambda/{app_name}-version-consolidator-{environment}",
    retention_in_days=14,
    tags=tags,
)

# Version consolidator Lambda
version_consolidator_lambda = aws.lambda_.Function(
    f"{app_name}-version-consolidator-{environment}",
    name=f"{app_name}-version-consolidator-{environment}",
    role=lambda_role.arn,
    handler="handlers.version_consolidator.version_consolidator_handler",
    runtime="python3.12",
    timeout=300,  # 5 minutes to consolidate results
    memory_size=512,  # More memory for processing large datasets
    code=pulumi.AssetArchive(
        {
            "index.py": pulumi.StringAsset(placeholder_lambda_code),
        }
    ),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "ENVIRONMENT": environment,
            "RESULTS_BUCKET": state_bucket_name,
            "RESORTS_TABLE": f"{app_name}-resorts-{environment}",
            "AWS_REGION_NAME": aws_region,
            "RESORT_UPDATES_TOPIC_ARN": "",  # Will be set after topic creation
        }
    ),
    tags=tags,
    opts=pulumi.ResourceOptions(
        depends_on=[lambda_role, version_consolidator_log_group]
    ),
)

# Schedule version consolidator at 07:00 UTC (1 hour after scraper) - all environments
# Creates versioned snapshots for review before deployment
version_consolidator_schedule_rule = aws.cloudwatch.EventRule(
    f"{app_name}-version-consolidator-schedule-{environment}",
    name=f"{app_name}-version-consolidator-schedule-{environment}",
    description="Consolidate scraper results into versioned database snapshot at 07:00 UTC",
    schedule_expression="cron(0 7 * * ? *)",
    tags=tags,
)

version_consolidator_schedule_permission = aws.lambda_.Permission(
    f"{app_name}-vers-cons-schedule-perm-{environment}",
    action="lambda:InvokeFunction",
    function=version_consolidator_lambda.name,
    principal="events.amazonaws.com",
    source_arn=version_consolidator_schedule_rule.arn,
)

version_consolidator_schedule_target = aws.cloudwatch.EventTarget(
    f"{app_name}-vers-cons-sched-target-{environment}",
    rule=version_consolidator_schedule_rule.name,
    target_id=f"vers-cons-{environment}",  # Explicit short target_id
    arn=version_consolidator_lambda.arn,
    input='{"process_latest": true}',
)

# =============================================================================
# Notification Processor Lambda - Sends push notifications for snow/events
# =============================================================================

# Log group for notification processor
notification_processor_log_group = aws.cloudwatch.LogGroup(
    f"{app_name}-notification-processor-logs-{environment}",
    name=f"/aws/lambda/{app_name}-notification-processor-{environment}",
    retention_in_days=14,
    tags=tags,
)

# SNS Platform Application for APNs (iOS push notifications)
# APNs uses token-based authentication (.p8 key file)
# Required config:
#   pulumi config set --secret apnsPrivateKey "$(cat AuthKey_XXXXXX.p8)"
#   pulumi config set apnsKeyId "XXXXXXXXXX"
#   pulumi config set apnsTeamId "XXXXXXXXXX"
#   pulumi config set apnsBundleId "com.wouterdevriendt.snowtracker"

# Get APNs configuration (optional - only create platform app if credentials are set)
apns_private_key = config.get_secret("apnsPrivateKey")
apns_key_id = config.get("apnsKeyId")
apns_team_id = config.get("apnsTeamId") or "N324UX8D9M"  # Default to existing team ID
apns_bundle_id = config.get("apnsBundleId") or "com.wouterdevriendt.snowtracker"

# Only create APNs platform application if valid credentials are configured
# To configure: pulumi config set --secret apnsPrivateKey "$(cat AuthKey_XXXXXX.p8)"
#              pulumi config set apnsKeyId "XXXXXXXXXX"
apns_platform_app = None
apns_platform_app_arn = None

if apns_private_key and apns_key_id:
    apns_platform_app = aws.sns.PlatformApplication(
        f"{app_name}-apns-{environment}",
        name=f"{app_name}-apns-{environment}",
        platform="APNS_SANDBOX" if environment != "prod" else "APNS",
        # Token-based authentication credentials
        platform_credential=apns_private_key,
        platform_principal=apns_key_id,
        # Token-based auth attributes
        apple_platform_team_id=apns_team_id,
        apple_platform_bundle_id=apns_bundle_id,
        # Note: SNS PlatformApplication does not support tags
    )
    apns_platform_app_arn = apns_platform_app.arn
else:
    pulumi.log.warn(
        "APNs credentials not configured. Push notifications will not work until configured."
    )

# Lambda function for notification processing
notification_processor_lambda = aws.lambda_.Function(
    f"{app_name}-notification-processor-{environment}",
    name=f"{app_name}-notification-processor-{environment}",
    role=lambda_role.arn,
    handler="handlers.notification_processor.notification_handler",
    runtime="python3.12",
    timeout=300,  # 5 minutes for processing all users
    memory_size=256,
    code=pulumi.AssetArchive(
        {
            "index.py": pulumi.StringAsset(placeholder_lambda_code),
        }
    ),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "ENVIRONMENT": environment,
            "USER_PREFERENCES_TABLE": f"{app_name}-user-preferences-{environment}",
            "DEVICE_TOKENS_TABLE": f"{app_name}-device-tokens-{environment}",
            "WEATHER_CONDITIONS_TABLE": f"{app_name}-weather-conditions-{environment}",
            "RESORT_EVENTS_TABLE": f"{app_name}-resort-events-{environment}",
            "RESORTS_TABLE": f"{app_name}-resorts-{environment}",
            "AWS_REGION_NAME": aws_region,
            # APNs platform ARN is optional - notifications will be skipped if not configured
            "APNS_PLATFORM_APP_ARN": apns_platform_app_arn
            if apns_platform_app_arn
            else "",
        }
    ),
    tags=tags,
    opts=pulumi.ResourceOptions(
        depends_on=[lambda_role, notification_processor_log_group]
    ),
)

# CloudWatch Events rule to trigger notification processor every hour
notification_schedule_rule = aws.cloudwatch.EventRule(
    f"{app_name}-notification-schedule-{environment}",
    name=f"{app_name}-notification-schedule-{environment}",
    description="Trigger notification processor every hour",
    schedule_expression="rate(1 hour)",
    tags=tags,
)

# Permission for CloudWatch Events to invoke the notification Lambda
notification_schedule_permission = aws.lambda_.Permission(
    f"{app_name}-notification-schedule-permission-{environment}",
    action="lambda:InvokeFunction",
    function=notification_processor_lambda.name,
    principal="events.amazonaws.com",
    source_arn=notification_schedule_rule.arn,
)

# CloudWatch Events target to invoke the notification processor Lambda
notification_schedule_target = aws.cloudwatch.EventTarget(
    f"{app_name}-notification-schedule-target-{environment}",
    rule=notification_schedule_rule.name,
    arn=notification_processor_lambda.arn,
)

# API Gateway REST API
api_gateway = aws.apigateway.RestApi(
    f"{app_name}-api-{environment}",
    name=f"{app_name}-api-{environment}",
    description=f"Snow Quality Tracker API - {environment}",
    tags=tags,
)

# Health check resource
health_resource = aws.apigateway.Resource(
    f"{app_name}-health-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=api_gateway.root_resource_id,
    path_part="health",
)

# Health check method (MOCK integration for simple health check)
health_method = aws.apigateway.Method(
    f"{app_name}-health-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=health_resource.id,
    http_method="GET",
    authorization="NONE",
)

# Health check integration (MOCK)
health_integration = aws.apigateway.Integration(
    f"{app_name}-health-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=health_resource.id,
    http_method=health_method.http_method,
    type="MOCK",
    request_templates={"application/json": '{"statusCode": 200}'},
)

# Health check method response
health_method_response = aws.apigateway.MethodResponse(
    f"{app_name}-health-method-response-{environment}",
    rest_api=api_gateway.id,
    resource_id=health_resource.id,
    http_method=health_method.http_method,
    status_code="200",
    response_models={"application/json": "Empty"},
)

# Health check integration response
health_integration_response = aws.apigateway.IntegrationResponse(
    f"{app_name}-health-integration-response-{environment}",
    rest_api=api_gateway.id,
    resource_id=health_resource.id,
    http_method=health_method.http_method,
    status_code="200",
    response_templates={
        "application/json": '{"status": "healthy", "environment": "'
        + environment
        + '"}'
    },
    opts=pulumi.ResourceOptions(depends_on=[health_integration]),
)

# =============================================================================
# API Handler Lambda and Routes
# =============================================================================

# API Handler Lambda - handles all /api/v1/* requests
api_handler_lambda = aws.lambda_.Function(
    f"{app_name}-api-handler-{environment}",
    name=f"{app_name}-api-handler-{environment}",
    role=lambda_role.arn,
    handler="handlers.api_handler.api_handler",
    runtime="python3.12",
    timeout=30,
    memory_size=256,
    publish=True,  # Required for SnapStart
    snap_start=aws.lambda_.FunctionSnapStartArgs(
        apply_on="PublishedVersions"  # Enable SnapStart for faster cold starts
    ),
    code=pulumi.AssetArchive(
        {
            "api_handler.py": pulumi.StringAsset(
                """
import json
import boto3
import os
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION_NAME', 'us-west-2'))

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def handler(event, context):
    path = event.get('path', '')
    method = event.get('httpMethod', 'GET')
    path_params = event.get('pathParameters') or {}

    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }

    try:
        # GET /api/v1/resorts
        if path == '/api/v1/resorts' and method == 'GET':
            return get_resorts(headers)

        # GET /api/v1/resorts/{resortId}
        if path.startswith('/api/v1/resorts/') and '/conditions' not in path and method == 'GET':
            resort_id = path_params.get('resortId') or path.split('/')[-1]
            return get_resort(resort_id, headers)

        # GET /api/v1/resorts/{resortId}/conditions
        if '/conditions' in path and method == 'GET':
            parts = path.split('/')
            resort_id = path_params.get('resortId') or parts[-2]
            return get_conditions(resort_id, headers)

        # OPTIONS for CORS preflight
        if method == 'OPTIONS':
            return {'statusCode': 200, 'headers': headers, 'body': ''}

        return {
            'statusCode': 404,
            'headers': headers,
            'body': json.dumps({'error': 'Not found', 'path': path})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }

def get_resorts(headers):
    table = dynamodb.Table(os.environ['RESORTS_TABLE'])
    response = table.scan()
    items = response.get('Items', [])
    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps(items, default=decimal_default)
    }

def get_resort(resort_id, headers):
    table = dynamodb.Table(os.environ['RESORTS_TABLE'])
    response = table.get_item(Key={'resort_id': resort_id})
    item = response.get('Item')
    if not item:
        return {
            'statusCode': 404,
            'headers': headers,
            'body': json.dumps({'error': 'Resort not found'})
        }
    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps(item, default=decimal_default)
    }

def get_conditions(resort_id, headers):
    table = dynamodb.Table(os.environ['WEATHER_CONDITIONS_TABLE'])
    response = table.query(
        KeyConditionExpression='resort_id = :rid',
        ExpressionAttributeValues={':rid': resort_id},
        ScanIndexForward=False,
        Limit=10
    )
    items = response.get('Items', [])
    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps(items, default=decimal_default)
    }
"""
            ),
        }
    ),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "ENVIRONMENT": environment,
            "RESORTS_TABLE": f"{app_name}-resorts-{environment}",
            "WEATHER_CONDITIONS_TABLE": f"{app_name}-weather-conditions-{environment}",
            "USER_PREFERENCES_TABLE": f"{app_name}-user-preferences-{environment}",
            "FEEDBACK_TABLE": f"{app_name}-feedback-{environment}",
            "DEVICE_TOKENS_TABLE": f"{app_name}-device-tokens-{environment}",
            "RESORT_EVENTS_TABLE": f"{app_name}-resort-events-{environment}",
            "AWS_REGION_NAME": aws_region,
        }
    ),
    tags=tags,
    opts=pulumi.ResourceOptions(depends_on=[lambda_role, log_group]),
)

# Permission for API Gateway to invoke the API handler Lambda
api_handler_permission = aws.lambda_.Permission(
    f"{app_name}-api-handler-permission-{environment}",
    action="lambda:InvokeFunction",
    function=api_handler_lambda.name,
    principal="apigateway.amazonaws.com",
    source_arn=pulumi.Output.concat(api_gateway.execution_arn, "/*"),
)

# API v1 resource: /api
api_resource = aws.apigateway.Resource(
    f"{app_name}-api-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=api_gateway.root_resource_id,
    path_part="api",
)

# API v1 resource: /api/v1
api_v1_resource = aws.apigateway.Resource(
    f"{app_name}-api-v1-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=api_resource.id,
    path_part="v1",
)

# Resorts resource: /api/v1/resorts
resorts_resource = aws.apigateway.Resource(
    f"{app_name}-resorts-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=api_v1_resource.id,
    path_part="resorts",
)

# GET /api/v1/resorts
resorts_method = aws.apigateway.Method(
    f"{app_name}-resorts-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=resorts_resource.id,
    http_method="GET",
    authorization="NONE",
)

resorts_integration = aws.apigateway.Integration(
    f"{app_name}-resorts-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=resorts_resource.id,
    http_method=resorts_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Single resort resource: /api/v1/resorts/{resortId}
resort_resource = aws.apigateway.Resource(
    f"{app_name}-resort-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=resorts_resource.id,
    path_part="{resortId}",
)

# GET /api/v1/resorts/{resortId}
resort_method = aws.apigateway.Method(
    f"{app_name}-resort-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=resort_resource.id,
    http_method="GET",
    authorization="NONE",
)

resort_integration = aws.apigateway.Integration(
    f"{app_name}-resort-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=resort_resource.id,
    http_method=resort_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Conditions resource: /api/v1/resorts/{resortId}/conditions
conditions_resource = aws.apigateway.Resource(
    f"{app_name}-conditions-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=resort_resource.id,
    path_part="conditions",
)

# GET /api/v1/resorts/{resortId}/conditions
conditions_method = aws.apigateway.Method(
    f"{app_name}-conditions-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=conditions_resource.id,
    http_method="GET",
    authorization="NONE",
)

conditions_integration = aws.apigateway.Integration(
    f"{app_name}-conditions-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=conditions_resource.id,
    http_method=conditions_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Events resource: /api/v1/resorts/{resortId}/events
events_resource = aws.apigateway.Resource(
    f"{app_name}-events-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=resort_resource.id,
    path_part="events",
)

# GET /api/v1/resorts/{resortId}/events
events_get_method = aws.apigateway.Method(
    f"{app_name}-events-get-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=events_resource.id,
    http_method="GET",
    authorization="NONE",
)

events_get_integration = aws.apigateway.Integration(
    f"{app_name}-events-get-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=events_resource.id,
    http_method=events_get_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# POST /api/v1/resorts/{resortId}/events
events_post_method = aws.apigateway.Method(
    f"{app_name}-events-post-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=events_resource.id,
    http_method="POST",
    authorization="NONE",
)

events_post_integration = aws.apigateway.Integration(
    f"{app_name}-events-post-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=events_resource.id,
    http_method=events_post_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Single event resource: /api/v1/resorts/{resortId}/events/{eventId}
event_resource = aws.apigateway.Resource(
    f"{app_name}-event-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=events_resource.id,
    path_part="{eventId}",
)

# DELETE /api/v1/resorts/{resortId}/events/{eventId}
event_delete_method = aws.apigateway.Method(
    f"{app_name}-event-delete-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=event_resource.id,
    http_method="DELETE",
    authorization="NONE",
)

event_delete_integration = aws.apigateway.Integration(
    f"{app_name}-event-delete-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=event_resource.id,
    http_method=event_delete_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Batch conditions resource: /api/v1/conditions
batch_conditions_parent_resource = aws.apigateway.Resource(
    f"{app_name}-batch-conditions-parent-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=api_v1_resource.id,
    path_part="conditions",
)

# Batch conditions resource: /api/v1/conditions/batch
batch_conditions_resource = aws.apigateway.Resource(
    f"{app_name}-batch-conditions-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=batch_conditions_parent_resource.id,
    path_part="batch",
)

# GET /api/v1/conditions/batch
batch_conditions_method = aws.apigateway.Method(
    f"{app_name}-batch-conditions-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=batch_conditions_resource.id,
    http_method="GET",
    authorization="NONE",
)

batch_conditions_integration = aws.apigateway.Integration(
    f"{app_name}-batch-conditions-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=batch_conditions_resource.id,
    http_method=batch_conditions_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Snow quality batch resource: /api/v1/snow-quality
snow_quality_parent_resource = aws.apigateway.Resource(
    f"{app_name}-snow-quality-parent-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=api_v1_resource.id,
    path_part="snow-quality",
)

# Snow quality batch resource: /api/v1/snow-quality/batch
snow_quality_batch_resource = aws.apigateway.Resource(
    f"{app_name}-snow-quality-batch-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=snow_quality_parent_resource.id,
    path_part="batch",
)

# GET /api/v1/snow-quality/batch
snow_quality_batch_method = aws.apigateway.Method(
    f"{app_name}-snow-quality-batch-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=snow_quality_batch_resource.id,
    http_method="GET",
    authorization="NONE",
)

snow_quality_batch_integration = aws.apigateway.Integration(
    f"{app_name}-snow-quality-batch-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=snow_quality_batch_resource.id,
    http_method=snow_quality_batch_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Recommendations resource: /api/v1/recommendations
recommendations_resource = aws.apigateway.Resource(
    f"{app_name}-recommendations-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=api_v1_resource.id,
    path_part="recommendations",
)

# GET /api/v1/recommendations
recommendations_method = aws.apigateway.Method(
    f"{app_name}-recommendations-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=recommendations_resource.id,
    http_method="GET",
    authorization="NONE",
)

recommendations_integration = aws.apigateway.Integration(
    f"{app_name}-recommendations-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=recommendations_resource.id,
    http_method=recommendations_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Recommendations best resource: /api/v1/recommendations/best
recommendations_best_resource = aws.apigateway.Resource(
    f"{app_name}-recommendations-best-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=recommendations_resource.id,
    path_part="best",
)

# GET /api/v1/recommendations/best
recommendations_best_method = aws.apigateway.Method(
    f"{app_name}-recommendations-best-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=recommendations_best_resource.id,
    http_method="GET",
    authorization="NONE",
)

recommendations_best_integration = aws.apigateway.Integration(
    f"{app_name}-recommendations-best-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=recommendations_best_resource.id,
    http_method=recommendations_best_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# =============================================================================
# User API Routes (preferences, device tokens, notification settings)
# =============================================================================

# User resource: /api/v1/user
user_resource = aws.apigateway.Resource(
    f"{app_name}-user-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=api_v1_resource.id,
    path_part="user",
)

# Preferences resource: /api/v1/user/preferences
user_preferences_resource = aws.apigateway.Resource(
    f"{app_name}-user-preferences-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=user_resource.id,
    path_part="preferences",
)

# GET /api/v1/user/preferences
user_preferences_get_method = aws.apigateway.Method(
    f"{app_name}-user-preferences-get-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=user_preferences_resource.id,
    http_method="GET",
    authorization="NONE",
)

user_preferences_get_integration = aws.apigateway.Integration(
    f"{app_name}-user-preferences-get-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=user_preferences_resource.id,
    http_method=user_preferences_get_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# PUT /api/v1/user/preferences
user_preferences_put_method = aws.apigateway.Method(
    f"{app_name}-user-preferences-put-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=user_preferences_resource.id,
    http_method="PUT",
    authorization="NONE",
)

user_preferences_put_integration = aws.apigateway.Integration(
    f"{app_name}-user-preferences-put-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=user_preferences_resource.id,
    http_method=user_preferences_put_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Device tokens resource: /api/v1/user/device-tokens
device_tokens_resource = aws.apigateway.Resource(
    f"{app_name}-device-tokens-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=user_resource.id,
    path_part="device-tokens",
)

# POST /api/v1/user/device-tokens
device_tokens_post_method = aws.apigateway.Method(
    f"{app_name}-device-tokens-post-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=device_tokens_resource.id,
    http_method="POST",
    authorization="NONE",
)

device_tokens_post_integration = aws.apigateway.Integration(
    f"{app_name}-device-tokens-post-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=device_tokens_resource.id,
    http_method=device_tokens_post_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# GET /api/v1/user/device-tokens
device_tokens_get_method = aws.apigateway.Method(
    f"{app_name}-device-tokens-get-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=device_tokens_resource.id,
    http_method="GET",
    authorization="NONE",
)

device_tokens_get_integration = aws.apigateway.Integration(
    f"{app_name}-device-tokens-get-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=device_tokens_resource.id,
    http_method=device_tokens_get_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Notification settings resource: /api/v1/user/notification-settings
notification_settings_resource = aws.apigateway.Resource(
    f"{app_name}-notification-settings-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=user_resource.id,
    path_part="notification-settings",
)

# GET /api/v1/user/notification-settings
notification_settings_get_method = aws.apigateway.Method(
    f"{app_name}-notification-settings-get-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=notification_settings_resource.id,
    http_method="GET",
    authorization="NONE",
)

notification_settings_get_integration = aws.apigateway.Integration(
    f"{app_name}-notification-settings-get-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=notification_settings_resource.id,
    http_method=notification_settings_get_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# PUT /api/v1/user/notification-settings
notification_settings_put_method = aws.apigateway.Method(
    f"{app_name}-notification-settings-put-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=notification_settings_resource.id,
    http_method="PUT",
    authorization="NONE",
)

notification_settings_put_integration = aws.apigateway.Integration(
    f"{app_name}-notification-settings-put-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=notification_settings_resource.id,
    http_method=notification_settings_put_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Resort notification settings: /api/v1/user/notification-settings/resorts
resort_notification_settings_resource = aws.apigateway.Resource(
    f"{app_name}-resort-notification-settings-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=notification_settings_resource.id,
    path_part="resorts",
)

# Single resort notification settings: /api/v1/user/notification-settings/resorts/{resortId}
resort_notification_setting_resource = aws.apigateway.Resource(
    f"{app_name}-resort-notification-setting-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=resort_notification_settings_resource.id,
    path_part="{resortId}",
)

# PUT /api/v1/user/notification-settings/resorts/{resortId}
resort_notification_setting_put_method = aws.apigateway.Method(
    f"{app_name}-resort-notification-setting-put-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=resort_notification_setting_resource.id,
    http_method="PUT",
    authorization="NONE",
)

resort_notification_setting_put_integration = aws.apigateway.Integration(
    f"{app_name}-resort-notification-setting-put-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=resort_notification_setting_resource.id,
    http_method=resort_notification_setting_put_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# DELETE /api/v1/user/notification-settings/resorts/{resortId}
resort_notification_setting_delete_method = aws.apigateway.Method(
    f"{app_name}-resort-notification-setting-delete-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=resort_notification_setting_resource.id,
    http_method="DELETE",
    authorization="NONE",
)

resort_notification_setting_delete_integration = aws.apigateway.Integration(
    f"{app_name}-resort-notification-setting-delete-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=resort_notification_setting_resource.id,
    http_method=resort_notification_setting_delete_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# =============================================================================
# Feedback API Route
# =============================================================================

# Feedback resource: /api/v1/feedback
feedback_resource = aws.apigateway.Resource(
    f"{app_name}-feedback-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=api_v1_resource.id,
    path_part="feedback",
)

# POST /api/v1/feedback
feedback_post_method = aws.apigateway.Method(
    f"{app_name}-feedback-post-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=feedback_resource.id,
    http_method="POST",
    authorization="NONE",
)

feedback_post_integration = aws.apigateway.Integration(
    f"{app_name}-feedback-post-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=feedback_resource.id,
    http_method=feedback_post_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# =============================================================================
# Debug API Routes (for testing notifications)
# =============================================================================

# Debug resource: /api/v1/debug
debug_resource = aws.apigateway.Resource(
    f"{app_name}-debug-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=api_v1_resource.id,
    path_part="debug",
)

# Trigger notifications resource: /api/v1/debug/trigger-notifications
debug_trigger_notifications_resource = aws.apigateway.Resource(
    f"{app_name}-debug-trigger-notifications-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=debug_resource.id,
    path_part="trigger-notifications",
)

# POST /api/v1/debug/trigger-notifications
debug_trigger_notifications_method = aws.apigateway.Method(
    f"{app_name}-debug-trigger-notifications-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=debug_trigger_notifications_resource.id,
    http_method="POST",
    authorization="NONE",
)

debug_trigger_notifications_integration = aws.apigateway.Integration(
    f"{app_name}-debug-trigger-notifications-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=debug_trigger_notifications_resource.id,
    http_method=debug_trigger_notifications_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# Test push notification resource: /api/v1/debug/test-push-notification
debug_test_push_resource = aws.apigateway.Resource(
    f"{app_name}-debug-test-push-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=debug_resource.id,
    path_part="test-push-notification",
)

# POST /api/v1/debug/test-push-notification
debug_test_push_method = aws.apigateway.Method(
    f"{app_name}-debug-test-push-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=debug_test_push_resource.id,
    http_method="POST",
    authorization="NONE",
)

debug_test_push_integration = aws.apigateway.Integration(
    f"{app_name}-debug-test-push-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=debug_test_push_resource.id,
    http_method=debug_test_push_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# =============================================================================
# Admin API Routes (for maintenance operations)
# =============================================================================

# Admin resource: /api/v1/admin
admin_resource = aws.apigateway.Resource(
    f"{app_name}-admin-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=api_v1_resource.id,
    path_part="admin",
)

# Backfill geohashes resource: /api/v1/admin/backfill-geohashes
admin_backfill_geohashes_resource = aws.apigateway.Resource(
    f"{app_name}-admin-backfill-geohashes-resource-{environment}",
    rest_api=api_gateway.id,
    parent_id=admin_resource.id,
    path_part="backfill-geohashes",
)

# POST /api/v1/admin/backfill-geohashes
admin_backfill_geohashes_method = aws.apigateway.Method(
    f"{app_name}-admin-backfill-geohashes-method-{environment}",
    rest_api=api_gateway.id,
    resource_id=admin_backfill_geohashes_resource.id,
    http_method="POST",
    authorization="NONE",
)

admin_backfill_geohashes_integration = aws.apigateway.Integration(
    f"{app_name}-admin-backfill-geohashes-integration-{environment}",
    rest_api=api_gateway.id,
    resource_id=admin_backfill_geohashes_resource.id,
    http_method=admin_backfill_geohashes_method.http_method,
    integration_http_method="POST",
    type="AWS_PROXY",
    uri=api_handler_lambda.invoke_arn,
)

# API Gateway Deployment (depends on all integrations)
# Note: triggers parameter forces recreation when routes change
api_deployment = aws.apigateway.Deployment(
    f"{app_name}-api-deployment-{environment}",
    rest_api=api_gateway.id,
    stage_name=environment,
    triggers={
        # Force redeployment when any integration changes
        "redeployment": pulumi.Output.all(
            health_integration_response.id,
            resorts_integration.id,
            resort_integration.id,
            conditions_integration.id,
            events_get_integration.id,
            events_post_integration.id,
            event_delete_integration.id,
            batch_conditions_integration.id,
            snow_quality_batch_integration.id,
            recommendations_integration.id,
            recommendations_best_integration.id,
            user_preferences_get_integration.id,
            user_preferences_put_integration.id,
            device_tokens_post_integration.id,
            device_tokens_get_integration.id,
            notification_settings_get_integration.id,
            notification_settings_put_integration.id,
            resort_notification_setting_put_integration.id,
            resort_notification_setting_delete_integration.id,
            feedback_post_integration.id,
            debug_trigger_notifications_integration.id,
            debug_test_push_integration.id,
            admin_backfill_geohashes_integration.id,
        ).apply(lambda ids: ",".join(ids)),
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            health_integration_response,
            resorts_integration,
            resort_integration,
            conditions_integration,
            events_get_integration,
            events_post_integration,
            event_delete_integration,
            batch_conditions_integration,
            snow_quality_batch_integration,
            recommendations_integration,
            recommendations_best_integration,
            user_preferences_get_integration,
            user_preferences_put_integration,
            device_tokens_post_integration,
            device_tokens_get_integration,
            notification_settings_get_integration,
            notification_settings_put_integration,
            resort_notification_setting_put_integration,
            resort_notification_setting_delete_integration,
            feedback_post_integration,
            debug_trigger_notifications_integration,
            debug_test_push_integration,
            admin_backfill_geohashes_integration,
        ]
    ),
)

# Cognito User Pool for authentication
user_pool = aws.cognito.UserPool(
    f"{app_name}-user-pool-{environment}",
    name=f"{app_name}-users-{environment}",
    auto_verified_attributes=["email"],
    password_policy={
        "minimum_length": 8,
        "require_lowercase": True,
        "require_numbers": True,
        "require_symbols": False,
        "require_uppercase": True,
    },
    username_attributes=["email"],
    tags=tags,
)

user_pool_client = aws.cognito.UserPoolClient(
    f"{app_name}-user-pool-client-{environment}",
    name=f"{app_name}-client-{environment}",
    user_pool_id=user_pool.id,
    generate_secret=False,
    explicit_auth_flows=["ADMIN_NO_SRP_AUTH", "USER_PASSWORD_AUTH"],
)

# API Gateway Monitoring (CloudWatch dashboards and alarms)
api_monitoring = create_api_gateway_monitoring(
    app_name=app_name, environment=environment, api_gateway_id=api_gateway.id, tags=tags
)

# Amazon Managed Grafana - single workspace for all environments (~$9/month per editor)
# Created only during staging deployment to avoid duplicate resources
monitoring_stack = create_monitoring_stack(
    app_name=app_name,
    environment=environment,
    tags=tags,
    create_grafana=(environment == "staging"),
)

# =============================================================================
# Custom Domain (powderchaserapp.com) - All Environments
# =============================================================================

# Domain was registered via Route53 in the [personal] account
# All environments use subdomains:
#   prod:    api.powderchaserapp.com
#   staging: staging.api.powderchaserapp.com
#   dev:     dev.api.powderchaserapp.com
enable_custom_domain = True
domain_name = "powderchaserapp.com"

# API subdomain varies by environment
if environment == "prod":
    api_subdomain = f"api.{domain_name}"
else:
    api_subdomain = f"{environment}.api.{domain_name}"

# Get the hosted zone (created automatically by Route53 domain registration)
hosted_zone = None
certificate = None
cert_validation = None
api_domain = None
website_distribution = None

if enable_custom_domain:
    # Get the hosted zone for the domain
    hosted_zone = aws.route53.get_zone(name=domain_name)

    # CloudFront certificate (for main website) - prod only
    # Must be in us-east-1 for CloudFront
    us_east_1 = aws.Provider("us-east-1", region="us-east-1")

    if environment == "prod":
        certificate = aws.acm.Certificate(
            f"{app_name}-certificate-{environment}",
            domain_name=domain_name,
            subject_alternative_names=[f"*.{domain_name}"],
            validation_method="DNS",
            tags=tags,
            opts=pulumi.ResourceOptions(provider=us_east_1),
        )

        # DNS validation record for wildcard cert
        # Note: ACM uses the same DNS record for both main domain and wildcard
        # so we only need to create one record (not two)
        # allow_overwrite handles cases where the record already exists
        cert_validation_record = aws.route53.Record(
            f"{app_name}-cert-validation-{environment}",
            zone_id=hosted_zone.zone_id,
            name=certificate.domain_validation_options[0].resource_record_name,
            type=certificate.domain_validation_options[0].resource_record_type,
            records=[certificate.domain_validation_options[0].resource_record_value],
            ttl=300,
            allow_overwrite=True,
            opts=pulumi.ResourceOptions(provider=us_east_1),
        )

        # Wait for certificate validation
        cert_validation = aws.acm.CertificateValidation(
            f"{app_name}-cert-validation-{environment}",
            certificate_arn=certificate.arn,
            validation_record_fqdns=[cert_validation_record.fqdn],
            opts=pulumi.ResourceOptions(provider=us_east_1),
        )

# =============================================================================
# Marketing Website (powderchaserapp.com) - S3 + CloudFront
# =============================================================================

# S3 bucket for website static files
website_bucket = aws.s3.BucketV2(
    f"{app_name}-website-{environment}",
    bucket=f"{app_name}-website-{environment}-{caller_identity.account_id}",
    tags=tags,
)

# Block public access - settings depend on environment
# Prod: fully blocked (CloudFront uses OAC)
# Non-prod: allow public bucket policy for static JSON API access
website_bucket_public_access_block = aws.s3.BucketPublicAccessBlock(
    f"{app_name}-website-pab-{environment}",
    bucket=website_bucket.id,
    block_public_acls=True,
    block_public_policy=(environment == "prod"),  # Allow public policy for non-prod
    ignore_public_acls=True,
    restrict_public_buckets=(
        environment == "prod"
    ),  # Allow public buckets for non-prod
)

# Website bucket configuration (for S3 website hosting fallback)
website_bucket_website = aws.s3.BucketWebsiteConfigurationV2(
    f"{app_name}-website-config-{environment}",
    bucket=website_bucket.id,
    index_document=aws.s3.BucketWebsiteConfigurationV2IndexDocumentArgs(
        suffix="index.html",
    ),
    error_document=aws.s3.BucketWebsiteConfigurationV2ErrorDocumentArgs(
        key="index.html",  # SPA fallback
    ),
)

# CloudFront Origin Access Control
website_oac = aws.cloudfront.OriginAccessControl(
    f"{app_name}-website-oac-{environment}",
    name=f"{app_name}-website-oac-{environment}",
    origin_access_control_origin_type="s3",
    signing_behavior="always",
    signing_protocol="sigv4",
)

# Website with CloudFront - prod only (powderchaserapp.com)
if environment == "prod" and cert_validation:
    # CloudFront distribution for marketing website with custom domain
    website_distribution = aws.cloudfront.Distribution(
        f"{app_name}-website-cdn-{environment}",
        enabled=True,
        is_ipv6_enabled=True,
        default_root_object="index.html",
        aliases=[domain_name],
        origins=[
            aws.cloudfront.DistributionOriginArgs(
                domain_name=website_bucket.bucket_regional_domain_name,
                origin_id="S3Origin",
                origin_access_control_id=website_oac.id,
            ),
        ],
        default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
            allowed_methods=["GET", "HEAD", "OPTIONS"],
            cached_methods=["GET", "HEAD"],
            target_origin_id="S3Origin",
            viewer_protocol_policy="redirect-to-https",
            compress=True,
            forwarded_values=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesArgs(
                query_string=False,
                cookies=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesCookiesArgs(
                    forward="none",
                ),
            ),
            min_ttl=0,
            default_ttl=86400,
            max_ttl=31536000,
        ),
        custom_error_responses=[
            # SPA routing - return index.html for 404s
            aws.cloudfront.DistributionCustomErrorResponseArgs(
                error_code=404,
                response_code=200,
                response_page_path="/index.html",
            ),
            aws.cloudfront.DistributionCustomErrorResponseArgs(
                error_code=403,
                response_code=200,
                response_page_path="/index.html",
            ),
        ],
        restrictions=aws.cloudfront.DistributionRestrictionsArgs(
            geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
                restriction_type="none",
            ),
        ),
        viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
            acm_certificate_arn=cert_validation.certificate_arn,
            ssl_support_method="sni-only",
            minimum_protocol_version="TLSv1.2_2021",
        ),
        tags=tags,
    )

    # S3 bucket policy to allow CloudFront access
    website_bucket_policy = aws.s3.BucketPolicy(
        f"{app_name}-website-policy-{environment}",
        bucket=website_bucket.id,
        policy=pulumi.Output.all(website_bucket.arn, website_distribution.arn).apply(
            lambda args: f"""{{
                "Version": "2012-10-17",
                "Statement": [{{
                    "Sid": "AllowCloudFrontServicePrincipal",
                    "Effect": "Allow",
                    "Principal": {{"Service": "cloudfront.amazonaws.com"}},
                    "Action": "s3:GetObject",
                    "Resource": "{args[0]}/*",
                    "Condition": {{"StringEquals": {{"AWS:SourceArn": "{args[1]}"}}}}
                }}]
            }}"""
        ),
    )

    # Route53 record for website (powderchaserapp.com -> CloudFront)
    website_dns_record = aws.route53.Record(
        f"{app_name}-website-dns-{environment}",
        zone_id=hosted_zone.zone_id,
        name=domain_name,
        type="A",
        aliases=[
            aws.route53.RecordAliasArgs(
                name=website_distribution.domain_name,
                zone_id=website_distribution.hosted_zone_id,
                evaluate_target_health=False,
            )
        ],
    )
else:
    # Non-prod: bucket policy allows public read access to the data/ folder
    # This enables direct S3 website endpoint access for static JSON API
    website_bucket_policy = aws.s3.BucketPolicy(
        f"{app_name}-website-policy-{environment}",
        bucket=website_bucket.id,
        policy=website_bucket.arn.apply(
            lambda arn: f"""{{
                "Version": "2012-10-17",
                "Statement": [{{
                    "Sid": "AllowPublicReadData",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": "{arn}/data/*"
                }}]
            }}"""
        ),
        opts=pulumi.ResourceOptions(depends_on=[website_bucket_public_access_block]),
    )

# =============================================================================
# API Custom Domain (all environments)
# - prod:    api.powderchaserapp.com
# - staging: staging.api.powderchaserapp.com
# - dev:     dev.api.powderchaserapp.com
# =============================================================================

if enable_custom_domain:
    # Get the hosted zone for the domain
    if hosted_zone is None:
        hosted_zone = aws.route53.get_zone(name=domain_name)

    # API Gateway custom domain requires regional certificate (us-west-2)
    api_regional_cert = aws.acm.Certificate(
        f"{app_name}-api-certificate-{environment}",
        domain_name=api_subdomain,
        validation_method="DNS",
        tags=tags,
    )

    api_cert_validation_record = aws.route53.Record(
        f"{app_name}-api-cert-validation-{environment}",
        zone_id=hosted_zone.zone_id,
        name=api_regional_cert.domain_validation_options[0].resource_record_name,
        type=api_regional_cert.domain_validation_options[0].resource_record_type,
        records=[api_regional_cert.domain_validation_options[0].resource_record_value],
        ttl=300,
        allow_overwrite=True,
    )

    api_cert_validation = aws.acm.CertificateValidation(
        f"{app_name}-api-cert-validation-wait-{environment}",
        certificate_arn=api_regional_cert.arn,
        validation_record_fqdns=[api_cert_validation_record.fqdn],
    )

    # API Gateway custom domain
    api_domain = aws.apigateway.DomainName(
        f"{app_name}-api-domain-{environment}",
        domain_name=api_subdomain,
        regional_certificate_arn=api_cert_validation.certificate_arn,
        endpoint_configuration=aws.apigateway.DomainNameEndpointConfigurationArgs(
            types="REGIONAL",
        ),
        tags=tags,
    )

    # API Gateway base path mapping
    api_mapping = aws.apigateway.BasePathMapping(
        f"{app_name}-api-mapping-{environment}",
        rest_api=api_gateway.id,
        stage_name=api_deployment.stage_name,
        domain_name=api_domain.domain_name,
    )

    # Route53 record for API
    api_dns_record = aws.route53.Record(
        f"{app_name}-api-dns-{environment}",
        zone_id=hosted_zone.zone_id,
        name=api_subdomain,
        type="A",
        aliases=[
            aws.route53.RecordAliasArgs(
                name=api_domain.regional_domain_name,
                zone_id=api_domain.regional_zone_id,
                evaluate_target_health=False,
            )
        ],
    )

# Exports
pulumi.export("pulumi_state_bucket", pulumi_state_bucket.bucket)
pulumi.export("resorts_table_name", resorts_table.name)
pulumi.export("weather_conditions_table_name", weather_conditions_table.name)
pulumi.export("user_preferences_table_name", user_preferences_table.name)
pulumi.export("feedback_table_name", feedback_table.name)
pulumi.export("device_tokens_table_name", device_tokens_table.name)
pulumi.export("resort_events_table_name", resort_events_table.name)
pulumi.export("snow_summary_table_name", snow_summary_table.name)
pulumi.export("lambda_role_arn", lambda_role.arn)
pulumi.export("api_gateway_id", api_gateway.id)
pulumi.export("api_gateway_url", api_deployment.invoke_url)
# SNS Topic for resort updates notifications
resort_updates_topic = aws.sns.Topic(
    f"{app_name}-resort-updates-{environment}",
    name=f"{app_name}-resort-updates-{environment}",
    tags=tags,
)

# Email subscription for resort updates (only in prod)
if environment == "prod":
    resort_updates_subscription = aws.sns.TopicSubscription(
        f"{app_name}-resort-updates-email-{environment}",
        topic=resort_updates_topic.arn,
        protocol="email",
        endpoint="wouterdevriendt@gmail.com",
    )

# =============================================================================
# SES Email Forwarding (support@powderchaserapp.com -> Gmail)
# =============================================================================
# Only set up in prod to avoid duplicate MX records
if environment == "prod" and hosted_zone is not None:
    forward_to_email = "wouterdevriendt@gmail.com"

    # SES Domain Identity - verify the domain for sending/receiving
    ses_domain_identity = aws.ses.DomainIdentity(
        f"{app_name}-ses-domain",
        domain=domain_name,
    )

    # DKIM for email authentication
    ses_domain_dkim = aws.ses.DomainDkim(
        f"{app_name}-ses-dkim",
        domain=ses_domain_identity.domain,
    )

    # Route53 DKIM records (3 CNAME records for DKIM verification)
    ses_dkim_records = []
    for i in range(3):
        record = aws.route53.Record(
            f"{app_name}-ses-dkim-record-{i}",
            zone_id=hosted_zone.zone_id,
            name=ses_domain_dkim.dkim_tokens[i].apply(
                lambda t: f"{t}._domainkey.{domain_name}"
            ),
            type="CNAME",
            ttl=300,
            records=[
                ses_domain_dkim.dkim_tokens[i].apply(
                    lambda t: f"{t}.dkim.amazonses.com"
                )
            ],
        )
        ses_dkim_records.append(record)

    # MX record for receiving emails via SES
    ses_mx_record = aws.route53.Record(
        f"{app_name}-ses-mx-record",
        zone_id=hosted_zone.zone_id,
        name=domain_name,
        type="MX",
        ttl=300,
        records=["10 inbound-smtp.us-west-2.amazonaws.com"],
    )

    # SPF record for sending authentication
    ses_spf_record = aws.route53.Record(
        f"{app_name}-ses-spf-record",
        zone_id=hosted_zone.zone_id,
        name=domain_name,
        type="TXT",
        ttl=300,
        records=["v=spf1 include:amazonses.com ~all"],
    )

    # S3 bucket to store incoming emails temporarily
    ses_email_bucket = aws.s3.BucketV2(
        f"{app_name}-ses-emails",
        bucket=f"{app_name}-ses-emails-{aws_region}",
        tags=tags,
    )

    # Lifecycle rule to delete old emails after 7 days
    ses_email_bucket_lifecycle = aws.s3.BucketLifecycleConfigurationV2(
        f"{app_name}-ses-emails-lifecycle",
        bucket=ses_email_bucket.id,
        rules=[
            aws.s3.BucketLifecycleConfigurationV2RuleArgs(
                id="delete-old-emails",
                status="Enabled",
                expiration=aws.s3.BucketLifecycleConfigurationV2RuleExpirationArgs(
                    days=7,
                ),
            )
        ],
    )

    # S3 bucket policy to allow SES to write emails
    ses_email_bucket_policy = aws.s3.BucketPolicy(
        f"{app_name}-ses-emails-policy",
        bucket=ses_email_bucket.id,
        policy=pulumi.Output.all(ses_email_bucket.arn).apply(
            lambda args: f"""{{
                "Version": "2012-10-17",
                "Statement": [
                    {{
                        "Sid": "AllowSESPuts",
                        "Effect": "Allow",
                        "Principal": {{
                            "Service": "ses.amazonaws.com"
                        }},
                        "Action": "s3:PutObject",
                        "Resource": "{args[0]}/*",
                        "Condition": {{
                            "StringEquals": {{
                                "AWS:SourceAccount": "{aws.get_caller_identity().account_id}"
                            }}
                        }}
                    }}
                ]
            }}"""
        ),
    )

    # Lambda function to forward emails
    email_forwarder_role = aws.iam.Role(
        f"{app_name}-email-forwarder-role",
        assume_role_policy="""{
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "sts:AssumeRole",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                },
                "Effect": "Allow"
            }]
        }""",
        tags=tags,
    )

    # Policy for email forwarder Lambda
    email_forwarder_policy = aws.iam.RolePolicy(
        f"{app_name}-email-forwarder-policy",
        role=email_forwarder_role.id,
        policy=pulumi.Output.all(ses_email_bucket.arn).apply(
            lambda args: f"""{{
                "Version": "2012-10-17",
                "Statement": [
                    {{
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents"
                        ],
                        "Resource": "arn:aws:logs:*:*:*"
                    }},
                    {{
                        "Effect": "Allow",
                        "Action": ["s3:GetObject"],
                        "Resource": "{args[0]}/*"
                    }},
                    {{
                        "Effect": "Allow",
                        "Action": ["ses:SendRawEmail"],
                        "Resource": "*"
                    }}
                ]
            }}"""
        ),
    )

    # Email forwarder Lambda code
    email_forwarder_code = f'''
import boto3
import email
import os
import re

def handler(event, context):
    """Forward incoming SES emails to Gmail."""
    s3 = boto3.client("s3")
    ses = boto3.client("ses", region_name="{aws_region}")

    forward_to = os.environ["FORWARD_TO"]
    sender_domain = os.environ["SENDER_DOMAIN"]

    for record in event.get("Records", []):
        # Get email from S3
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        response = s3.get_object(Bucket=bucket, Key=key)
        raw_email = response["Body"].read()

        # Parse email
        msg = email.message_from_bytes(raw_email)
        original_from = msg.get("From", "unknown")
        original_to = msg.get("To", "")
        subject = msg.get("Subject", "(no subject)")

        # Create forwarded email
        # Replace From with our domain (required by SES)
        # Put original sender in Reply-To
        del msg["From"]
        del msg["Return-Path"]
        del msg["DKIM-Signature"]

        msg["From"] = f"support@{{sender_domain}}"
        msg["Reply-To"] = original_from
        msg["X-Original-From"] = original_from
        msg["X-Original-To"] = original_to

        # Prefix subject with [Fwd]
        del msg["Subject"]
        msg["Subject"] = f"[Fwd] {{subject}}"

        # Send via SES
        ses.send_raw_email(
            Source=f"support@{{sender_domain}}",
            Destinations=[forward_to],
            RawMessage={{"Data": msg.as_bytes()}}
        )

        print(f"Forwarded email from {{original_from}} to {{forward_to}}")

    return {{"status": "ok"}}
'''

    # Create Lambda function for email forwarding
    email_forwarder_lambda = aws.lambda_.Function(
        f"{app_name}-email-forwarder",
        role=email_forwarder_role.arn,
        runtime="python3.11",
        handler="index.handler",
        timeout=30,
        memory_size=256,
        code=pulumi.AssetArchive(
            {"index.py": pulumi.StringAsset(email_forwarder_code)}
        ),
        environment=aws.lambda_.FunctionEnvironmentArgs(
            variables={
                "FORWARD_TO": forward_to_email,
                "SENDER_DOMAIN": domain_name,
            }
        ),
        tags=tags,
    )

    # Allow S3 to invoke Lambda
    email_forwarder_s3_permission = aws.lambda_.Permission(
        f"{app_name}-email-forwarder-s3-permission",
        action="lambda:InvokeFunction",
        function=email_forwarder_lambda.name,
        principal="s3.amazonaws.com",
        source_arn=ses_email_bucket.arn,
    )

    # S3 notification to trigger Lambda when new email arrives
    ses_email_bucket_notification = aws.s3.BucketNotification(
        f"{app_name}-ses-emails-notification",
        bucket=ses_email_bucket.id,
        lambda_functions=[
            aws.s3.BucketNotificationLambdaFunctionArgs(
                lambda_function_arn=email_forwarder_lambda.arn,
                events=["s3:ObjectCreated:*"],
            )
        ],
        opts=pulumi.ResourceOptions(depends_on=[email_forwarder_s3_permission]),
    )

    # SES Receipt Rule Set (active rule set for receiving emails)
    ses_rule_set = aws.ses.ReceiptRuleSet(
        f"{app_name}-ses-rule-set",
        rule_set_name=f"{app_name}-email-rules",
    )

    # Activate the rule set
    ses_active_rule_set = aws.ses.ActiveReceiptRuleSet(
        f"{app_name}-ses-active-rule-set",
        rule_set_name=ses_rule_set.rule_set_name,
    )

    # SES Receipt Rule - save emails to S3 (which triggers Lambda)
    ses_receipt_rule = aws.ses.ReceiptRule(
        f"{app_name}-ses-receipt-rule",
        rule_set_name=ses_rule_set.rule_set_name,
        name="forward-to-gmail",
        enabled=True,
        scan_enabled=True,
        recipients=[f"support@{domain_name}"],
        s3_actions=[
            aws.ses.ReceiptRuleS3ActionArgs(
                bucket_name=ses_email_bucket.bucket,
                position=1,
            )
        ],
        opts=pulumi.ResourceOptions(
            depends_on=[ses_active_rule_set, ses_email_bucket_policy]
        ),
    )

    # SMTP credentials for sending FROM Gmail as support@powderchaserapp.com
    ses_smtp_user = aws.iam.User(
        f"{app_name}-ses-smtp-user",
        name=f"{app_name}-ses-smtp",
        tags=tags,
    )

    ses_smtp_policy = aws.iam.UserPolicy(
        f"{app_name}-ses-smtp-policy",
        user=ses_smtp_user.name,
        policy="""{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "ses:SendRawEmail",
                "Resource": "*"
            }]
        }""",
    )

    ses_smtp_access_key = aws.iam.AccessKey(
        f"{app_name}-ses-smtp-access-key",
        user=ses_smtp_user.name,
    )

    # Export SES email setup info
    pulumi.export("ses_smtp_server", "email-smtp.us-west-2.amazonaws.com")
    pulumi.export("ses_smtp_port", "587")
    pulumi.export("ses_smtp_username", ses_smtp_access_key.id)
    pulumi.export("ses_smtp_password", ses_smtp_access_key.ses_smtp_password_v4)
    pulumi.export("support_email", f"support@{domain_name}")
    pulumi.export(
        "gmail_send_as_instructions",
        pulumi.Output.concat(
            "To send from Gmail as support@powderchaserapp.com:\n",
            "1. Gmail Settings -> Accounts -> 'Send mail as' -> Add another email\n",
            "2. Email: support@powderchaserapp.com\n",
            "3. SMTP Server: email-smtp.us-west-2.amazonaws.com\n",
            "4. Port: 587, TLS: Yes\n",
            "5. Username: ",
            ses_smtp_access_key.id,
            "\n",
            "6. Password: (see ses_smtp_password output)\n",
        ),
    )

pulumi.export("user_pool_id", user_pool.id)
pulumi.export("user_pool_client_id", user_pool_client.id)
pulumi.export("region", aws_region)
pulumi.export("environment", environment)
pulumi.export("weather_processor_lambda_name", weather_processor_lambda.name)
pulumi.export("weather_worker_lambda_name", weather_worker_lambda.name)
pulumi.export("weather_schedule_rule_name", weather_schedule_rule.name)
pulumi.export("scraper_orchestrator_lambda_name", scraper_orchestrator_lambda.name)
pulumi.export("scraper_worker_lambda_name", scraper_worker_lambda.name)
pulumi.export(
    "scraper_results_processor_lambda_name", scraper_results_processor_lambda.name
)
pulumi.export("version_consolidator_lambda_name", version_consolidator_lambda.name)
pulumi.export("scraper_schedule_rule_name", scraper_schedule_rule.name)
pulumi.export("api_handler_lambda_name", api_handler_lambda.name)
pulumi.export("notification_processor_lambda_name", notification_processor_lambda.name)
pulumi.export("notification_schedule_rule_name", notification_schedule_rule.name)
pulumi.export("static_json_lambda_name", static_json_lambda.name)
pulumi.export("static_json_schedule_rule_name", static_json_schedule_rule.name)
if apns_platform_app:
    pulumi.export("apns_platform_app_arn", apns_platform_app.arn)
else:
    pulumi.export("apns_platform_app_arn", "not-configured")
pulumi.export("resort_updates_topic_arn", resort_updates_topic.arn)
pulumi.export("new_resorts_topic_arn", new_resorts_topic.arn)

# Monitoring exports
pulumi.export("cloudwatch_dashboard_name", api_monitoring["dashboard"].dashboard_name)
pulumi.export("alarm_topic_arn", api_monitoring["alarm_topic"].arn)

# Managed Grafana exports (created by staging, monitors all environments)
if "grafana_workspace" in monitoring_stack:
    pulumi.export("grafana_workspace_id", monitoring_stack["grafana_workspace"].id)
    pulumi.export(
        "grafana_workspace_endpoint", monitoring_stack["grafana_workspace"].endpoint
    )
    pulumi.export(
        "grafana_access_instructions",
        pulumi.Output.concat(
            "To access Amazon Managed Grafana:\n",
            "1. Navigate to the Grafana workspace endpoint in your browser\n",
            "2. Sign in using AWS SSO (IAM Identity Center)\n",
            "3. CloudWatch data source is pre-configured\n",
            "Note: You must configure AWS SSO users/groups with Grafana permissions",
        ),
    )

# Website and API exports
pulumi.export("website_bucket_name", website_bucket.bucket)

# API custom URL (all environments have subdomains)
if enable_custom_domain:
    pulumi.export("api_url_custom", f"https://{api_subdomain}")

# Website URL and CloudFront (prod only)
if environment == "prod" and website_distribution:
    pulumi.export("website_url", f"https://{domain_name}")
    pulumi.export("cloudfront_distribution_id", website_distribution.id)
    # Static JSON API URLs (served via CloudFront)
    pulumi.export("static_api_resorts_url", f"https://{domain_name}/data/resorts.json")
    pulumi.export(
        "static_api_snow_quality_url", f"https://{domain_name}/data/snow-quality.json"
    )
else:
    pulumi.export("website_url", website_bucket_website.website_endpoint)
    # Static JSON API URLs (served via S3 website endpoint)
    pulumi.export(
        "static_api_resorts_url",
        pulumi.Output.concat(
            "http://", website_bucket_website.website_endpoint, "/data/resorts.json"
        ),
    )
    pulumi.export(
        "static_api_snow_quality_url",
        pulumi.Output.concat(
            "http://",
            website_bucket_website.website_endpoint,
            "/data/snow-quality.json",
        ),
    )

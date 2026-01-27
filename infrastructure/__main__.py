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
    attributes=[{"name": "resort_id", "type": "S"}, {"name": "country", "type": "S"}],
    global_secondary_indexes=[
        {"name": "CountryIndex", "hash_key": "country", "projection_type": "ALL"}
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

# IAM Policy for Lambda to access DynamoDB and CloudWatch
lambda_policy = aws.iam.RolePolicy(
    f"{app_name}-lambda-policy-{environment}",
    role=lambda_role.id,
    policy=pulumi.Output.all(
        resorts_table.arn,
        weather_conditions_table.arn,
        user_preferences_table.arn,
        feedback_table.arn,
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
                    "dynamodb:Scan"
                ],
                "Resource": [
                    "{arns[0]}",
                    "{arns[1]}",
                    "{arns[2]}",
                    "{arns[3]}",
                    "{arns[0]}/index/*",
                    "{arns[1]}/index/*",
                    "{arns[2]}/index/*",
                    "{arns[3]}/index/*"
                ]
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

weather_processor_lambda = aws.lambda_.Function(
    f"{app_name}-weather-processor-{environment}",
    name=f"{app_name}-weather-processor-{environment}",
    role=lambda_role.arn,
    handler="handlers.weather_processor.weather_processor_handler",
    runtime="python3.12",
    timeout=300,  # 5 minutes for processing all resorts
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
            # Weather API key is set via AWS Secrets Manager or environment variable
            # For now, placeholder - will be configured via CI/CD secrets
        }
    ),
    tags=tags,
    opts=pulumi.ResourceOptions(depends_on=[lambda_role, weather_processor_log_group]),
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
            "FEEDBACK_TABLE": f"{app_name}-feedback-{environment}",
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
            batch_conditions_integration.id,
        ).apply(lambda ids: ",".join(ids)),
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            health_integration_response,
            resorts_integration,
            resort_integration,
            conditions_integration,
            batch_conditions_integration,
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

# Exports
pulumi.export("pulumi_state_bucket", pulumi_state_bucket.bucket)
pulumi.export("resorts_table_name", resorts_table.name)
pulumi.export("weather_conditions_table_name", weather_conditions_table.name)
pulumi.export("user_preferences_table_name", user_preferences_table.name)
pulumi.export("feedback_table_name", feedback_table.name)
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

pulumi.export("user_pool_id", user_pool.id)
pulumi.export("user_pool_client_id", user_pool_client.id)
pulumi.export("region", aws_region)
pulumi.export("environment", environment)
pulumi.export("weather_processor_lambda_name", weather_processor_lambda.name)
pulumi.export("weather_schedule_rule_name", weather_schedule_rule.name)
pulumi.export("api_handler_lambda_name", api_handler_lambda.name)
pulumi.export("resort_updates_topic_arn", resort_updates_topic.arn)

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

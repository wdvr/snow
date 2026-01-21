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
# Note: This bucket is used for storing Pulumi state after initial bootstrap
pulumi_state_bucket = aws.s3.Bucket(
    f"{app_name}-pulumi-state",
    bucket=f"{app_name}-pulumi-state-{aws_region}",
    versioning=aws.s3.BucketVersioningArgs(enabled=True),
    server_side_encryption_configuration=aws.s3.BucketServerSideEncryptionConfigurationArgs(
        rule=aws.s3.BucketServerSideEncryptionConfigurationRuleArgs(
            apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationRuleApplyServerSideEncryptionByDefaultArgs(
                sse_algorithm="AES256"
            )
        )
    ),
    lifecycle_rules=[
        aws.s3.BucketLifecycleRuleArgs(
            enabled=True,
            noncurrent_version_expiration=aws.s3.BucketLifecycleRuleNoncurrentVersionExpirationArgs(
                days=90
            ),
        )
    ],
    tags=tags,
)

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
        resorts_table.arn, weather_conditions_table.arn, user_preferences_table.arn
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
                    "{arns[0]}/index/*",
                    "{arns[1]}/index/*",
                    "{arns[2]}/index/*"
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
weather_processor_lambda = aws.lambda_.Function(
    f"{app_name}-weather-processor-{environment}",
    name=f"{app_name}-weather-processor-{environment}",
    role=lambda_role.arn,
    handler="handlers.weather_processor.handler",
    runtime="python3.12",
    timeout=300,  # 5 minutes for processing all resorts
    memory_size=256,
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

# API Gateway Deployment (placeholder - will be configured with actual endpoints)
api_deployment = aws.apigateway.Deployment(
    f"{app_name}-api-deployment-{environment}",
    rest_api=api_gateway.id,
    stage_name=environment,
    opts=pulumi.ResourceOptions(depends_on=[api_gateway]),
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

# EKS with Grafana/Prometheus (only for staging/prod)
# For dev, we use Lambda which is more cost-effective
enable_eks = config.get_bool("enableEks") or environment in ["staging", "prod"]
monitoring_stack = create_monitoring_stack(
    app_name=app_name, environment=environment, tags=tags, enable_eks=enable_eks
)

# Exports
pulumi.export("pulumi_state_bucket", pulumi_state_bucket.bucket)
pulumi.export("resorts_table_name", resorts_table.name)
pulumi.export("weather_conditions_table_name", weather_conditions_table.name)
pulumi.export("user_preferences_table_name", user_preferences_table.name)
pulumi.export("lambda_role_arn", lambda_role.arn)
pulumi.export("api_gateway_id", api_gateway.id)
pulumi.export("api_gateway_url", api_deployment.invoke_url)
pulumi.export("user_pool_id", user_pool.id)
pulumi.export("user_pool_client_id", user_pool_client.id)
pulumi.export("region", aws_region)
pulumi.export("environment", environment)
pulumi.export("weather_processor_lambda_name", weather_processor_lambda.name)
pulumi.export("weather_schedule_rule_name", weather_schedule_rule.name)

# Monitoring exports
pulumi.export("cloudwatch_dashboard_name", api_monitoring["dashboard"].dashboard_name)
pulumi.export("alarm_topic_arn", api_monitoring["alarm_topic"].arn)

# EKS exports (only when enabled)
if enable_eks and "eks_cluster" in monitoring_stack:
    pulumi.export("eks_cluster_name", monitoring_stack["eks_cluster"].name)
    pulumi.export("eks_kubeconfig", monitoring_stack["eks_cluster"].kubeconfig)

    # Grafana access instructions
    pulumi.export(
        "grafana_access_instructions",
        pulumi.Output.concat(
            "To access Grafana:\n",
            "1. Get the LoadBalancer URL: kubectl get svc -n monitoring grafana -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'\n",
            "2. Access Grafana at: http://<LoadBalancer-URL>:80\n",
            "3. Default credentials: admin / (set via grafanaAdminPassword config or 'admin')\n",
            "4. CloudWatch and Prometheus datasources are pre-configured",
        ),
    )

"""
Snow Quality Tracker - Monitoring Infrastructure

This module sets up:
- Amazon Managed Grafana for dashboards and visualization (single workspace for all envs)
- CloudWatch dashboards and alarms (per environment)
- SNS notifications for alerts
"""

import json

import pulumi
import pulumi_aws as aws


def create_unified_grafana_workspace(app_name: str, tags: dict):
    """
    Create a single Amazon Managed Grafana workspace for all environments.

    This workspace monitors dev, staging, and prod through CloudWatch,
    with dashboards organized by environment folders.

    Args:
        app_name: Application name for resource naming
        tags: Resource tags

    Returns:
        Dictionary of created resources including the workspace
    """
    resources = {}

    # Get account ID for IAM policy
    caller_identity = aws.get_caller_identity()

    grafana_assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "grafana.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": caller_identity.account_id}
                },
            }
        ],
    }

    # Single IAM role for the unified Grafana workspace
    grafana_role = aws.iam.Role(
        f"{app_name}-grafana-role",
        name=f"{app_name}-grafana-role",
        assume_role_policy=json.dumps(grafana_assume_role_policy),
        tags=tags,
    )
    resources["grafana_role"] = grafana_role

    # IAM policy for Grafana to read CloudWatch metrics and logs from ALL environments
    grafana_policy = aws.iam.RolePolicy(
        f"{app_name}-grafana-policy",
        role=grafana_role.id,
        policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "cloudwatch:DescribeAlarmsForMetric",
                            "cloudwatch:DescribeAlarmHistory",
                            "cloudwatch:DescribeAlarms",
                            "cloudwatch:ListMetrics",
                            "cloudwatch:GetMetricData",
                            "cloudwatch:GetMetricStatistics",
                            "cloudwatch:GetInsightRuleReport",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:DescribeLogGroups",
                            "logs:GetLogGroupFields",
                            "logs:StartQuery",
                            "logs:StopQuery",
                            "logs:GetQueryResults",
                            "logs:GetLogEvents",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ec2:DescribeSecurityGroups",
                            "ec2:DescribeSubnets",
                            "ec2:DescribeVpcs",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["tag:GetResources"],
                        "Resource": "*",
                    },
                ],
            }
        ),
    )
    resources["grafana_policy"] = grafana_policy

    # Single Amazon Managed Grafana workspace for all environments
    grafana_workspace = aws.grafana.Workspace(
        f"{app_name}-grafana",
        name=f"{app_name}-grafana",
        description="Snow Quality Tracker - Unified Monitoring (dev/staging/prod)",
        account_access_type="CURRENT_ACCOUNT",
        authentication_providers=["AWS_SSO"],
        permission_type="SERVICE_MANAGED",
        role_arn=grafana_role.arn,
        data_sources=["CLOUDWATCH", "PROMETHEUS"],
        notification_destinations=["SNS"],
        tags=tags,
        opts=pulumi.ResourceOptions(depends_on=[grafana_policy]),
    )
    resources["grafana_workspace"] = grafana_workspace

    pulumi.log.info(
        "Created unified Amazon Managed Grafana workspace for all environments"
    )

    return resources


def create_monitoring_stack(
    app_name: str,
    environment: str,
    tags: dict,
    vpc_id: str = None,
    enable_eks: bool = False,
    create_grafana: bool = False,
):
    """
    Create the monitoring infrastructure stack.

    Args:
        app_name: Application name for resource naming
        environment: Environment (dev/staging/prod)
        tags: Resource tags
        vpc_id: Optional existing VPC ID (not used for Managed Grafana)
        enable_eks: Deprecated - EKS is not used (kept for backward compatibility)
        create_grafana: If True, create the unified Grafana workspace (only set for one env)

    Returns:
        Dictionary of created resources
    """
    resources = {}

    # Create unified Grafana workspace only when explicitly requested
    # This should be done from only ONE environment's deployment (e.g., staging)
    # to avoid duplicate resource creation
    if create_grafana:
        grafana_resources = create_unified_grafana_workspace(app_name, tags)
        resources.update(grafana_resources)
    else:
        pulumi.log.info(
            f"Skipping Grafana creation for {environment} - managed by staging deployment"
        )

    return resources


def create_api_gateway_monitoring(
    app_name: str, environment: str, api_gateway_id: pulumi.Output, tags: dict
):
    """
    Create CloudWatch dashboards and alarms for API Gateway monitoring.
    """

    # CloudWatch Dashboard for API Gateway
    dashboard = aws.cloudwatch.Dashboard(
        f"{app_name}-api-dashboard-{environment}",
        dashboard_name=f"{app_name}-api-{environment}",
        dashboard_body=api_gateway_id.apply(
            lambda api_id: f"""{{
            "widgets": [
                {{
                    "type": "metric",
                    "x": 0,
                    "y": 0,
                    "width": 12,
                    "height": 6,
                    "properties": {{
                        "title": "API Requests",
                        "metrics": [
                            ["AWS/ApiGateway", "Count", "ApiName", "{app_name}-api-{environment}"]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": "us-west-2"
                    }}
                }},
                {{
                    "type": "metric",
                    "x": 12,
                    "y": 0,
                    "width": 12,
                    "height": 6,
                    "properties": {{
                        "title": "API Latency",
                        "metrics": [
                            ["AWS/ApiGateway", "Latency", "ApiName", "{app_name}-api-{environment}"]
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": "us-west-2"
                    }}
                }},
                {{
                    "type": "metric",
                    "x": 0,
                    "y": 6,
                    "width": 12,
                    "height": 6,
                    "properties": {{
                        "title": "4XX Errors",
                        "metrics": [
                            ["AWS/ApiGateway", "4XXError", "ApiName", "{app_name}-api-{environment}"]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": "us-west-2"
                    }}
                }},
                {{
                    "type": "metric",
                    "x": 12,
                    "y": 6,
                    "width": 12,
                    "height": 6,
                    "properties": {{
                        "title": "5XX Errors",
                        "metrics": [
                            ["AWS/ApiGateway", "5XXError", "ApiName", "{app_name}-api-{environment}"]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": "us-west-2"
                    }}
                }},
                {{
                    "type": "metric",
                    "x": 0,
                    "y": 12,
                    "width": 24,
                    "height": 6,
                    "properties": {{
                        "title": "DynamoDB Read/Write Capacity",
                        "metrics": [
                            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "{app_name}-resorts-{environment}"],
                            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", "{app_name}-resorts-{environment}"],
                            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "{app_name}-weather-conditions-{environment}"],
                            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", "{app_name}-weather-conditions-{environment}"]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": "us-west-2"
                    }}
                }}
            ]
        }}"""
        ),
    )

    # SNS Topic for alarms
    alarm_topic = aws.sns.Topic(
        f"{app_name}-alarm-topic-{environment}",
        name=f"{app_name}-alarms-{environment}",
        tags=tags,
    )

    # High Error Rate Alarm
    error_alarm = aws.cloudwatch.MetricAlarm(
        f"{app_name}-high-error-rate-{environment}",
        name=f"{app_name}-high-error-rate-{environment}",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=2,
        metric_name="5XXError",
        namespace="AWS/ApiGateway",
        period=300,
        statistic="Sum",
        threshold=10,
        alarm_description="API Gateway 5XX errors exceeded threshold",
        dimensions={"ApiName": f"{app_name}-api-{environment}"},
        alarm_actions=[alarm_topic.arn],
        ok_actions=[alarm_topic.arn],
        tags=tags,
    )

    # High Latency Alarm
    latency_alarm = aws.cloudwatch.MetricAlarm(
        f"{app_name}-high-latency-{environment}",
        name=f"{app_name}-high-latency-{environment}",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=3,
        metric_name="Latency",
        namespace="AWS/ApiGateway",
        period=300,
        statistic="Average",
        threshold=3000,  # 3 seconds
        alarm_description="API Gateway latency exceeded 3 seconds",
        dimensions={"ApiName": f"{app_name}-api-{environment}"},
        alarm_actions=[alarm_topic.arn],
        ok_actions=[alarm_topic.arn],
        tags=tags,
    )

    return {
        "dashboard": dashboard,
        "alarm_topic": alarm_topic,
        "error_alarm": error_alarm,
        "latency_alarm": latency_alarm,
    }

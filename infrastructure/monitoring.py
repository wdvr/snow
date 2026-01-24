"""
Snow Quality Tracker - Monitoring Infrastructure

This module sets up:
- Amazon Managed Grafana for dashboards and visualization
- CloudWatch dashboards and alarms
- SNS notifications for alerts
"""

import json

import pulumi
import pulumi_aws as aws


def create_monitoring_stack(
    app_name: str,
    environment: str,
    tags: dict,
    vpc_id: str = None,
    enable_eks: bool = False,
):
    """
    Create the monitoring infrastructure stack with Amazon Managed Grafana.

    Args:
        app_name: Application name for resource naming
        environment: Environment (dev/staging/prod)
        tags: Resource tags
        vpc_id: Optional existing VPC ID (not used for Managed Grafana)
        enable_eks: Deprecated - EKS is not used (kept for backward compatibility)

    Returns:
        Dictionary of created resources
    """
    resources = {}

    # Managed Grafana requires AWS SSO (IAM Identity Center) to be enabled.
    # Since SSO is not configured, skip Grafana for all environments and use CloudWatch.
    # To enable Grafana later:
    # 1. Set up AWS IAM Identity Center (SSO)
    # 2. Change the condition below back to: if environment != "prod":
    pulumi.log.info(
        f"Skipping Managed Grafana for {environment} - AWS SSO not configured. "
        "Use CloudWatch dashboards instead."
    )
    return resources

    # NOTE: Code below disabled until AWS SSO is configured
    if environment != "prod":
        pulumi.log.info(
            f"Skipping Managed Grafana for {environment} - use CloudWatch dashboards"
        )
        return resources

    # IAM role for Amazon Managed Grafana
    # Get account ID (synchronous call - returns actual value, not Output)
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

    grafana_role = aws.iam.Role(
        f"{app_name}-grafana-role-{environment}",
        name=f"{app_name}-grafana-role-{environment}",
        assume_role_policy=json.dumps(grafana_assume_role_policy),
        tags=tags,
    )
    resources["grafana_role"] = grafana_role

    # IAM policy for Grafana to read CloudWatch metrics and logs
    grafana_policy = aws.iam.RolePolicy(
        f"{app_name}-grafana-policy-{environment}",
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

    # Amazon Managed Grafana workspace
    grafana_workspace = aws.grafana.Workspace(
        f"{app_name}-grafana-{environment}",
        name=f"{app_name}-grafana-{environment}",
        description=f"Snow Quality Tracker Monitoring - {environment}",
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

    pulumi.log.info(f"Created Amazon Managed Grafana workspace for {environment}")

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

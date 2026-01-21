"""
Snow Quality Tracker - Monitoring Infrastructure

This module sets up:
- EKS cluster for running the API
- Grafana for monitoring and dashboards
- Prometheus for metrics collection
- CloudWatch integration
"""

import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts


def create_monitoring_stack(
    app_name: str,
    environment: str,
    tags: dict,
    vpc_id: str = None,
    enable_eks: bool = True
):
    """
    Create the monitoring infrastructure stack.

    Args:
        app_name: Application name for resource naming
        environment: Environment (dev/staging/prod)
        tags: Resource tags
        vpc_id: Optional existing VPC ID
        enable_eks: Whether to create EKS cluster (can be disabled for dev)

    Returns:
        Dictionary of created resources
    """
    resources = {}

    # Only create EKS for staging/prod (expensive for dev)
    if not enable_eks or environment == "dev":
        pulumi.log.info("Skipping EKS creation for dev environment - use Lambda instead")
        return resources

    # Create VPC for EKS if not provided
    if not vpc_id:
        vpc = aws.ec2.Vpc(
            f"{app_name}-vpc-{environment}",
            cidr_block="10.0.0.0/16",
            enable_dns_hostnames=True,
            enable_dns_support=True,
            tags={**tags, "Name": f"{app_name}-vpc-{environment}"}
        )
        resources["vpc"] = vpc

        # Create subnets across 2 AZs
        azs = ["us-west-2a", "us-west-2b"]
        public_subnets = []
        private_subnets = []

        for i, az in enumerate(azs):
            # Public subnet
            public_subnet = aws.ec2.Subnet(
                f"{app_name}-public-subnet-{i}-{environment}",
                vpc_id=vpc.id,
                cidr_block=f"10.0.{i * 2}.0/24",
                availability_zone=az,
                map_public_ip_on_launch=True,
                tags={
                    **tags,
                    "Name": f"{app_name}-public-{az}",
                    "kubernetes.io/role/elb": "1"
                }
            )
            public_subnets.append(public_subnet)

            # Private subnet
            private_subnet = aws.ec2.Subnet(
                f"{app_name}-private-subnet-{i}-{environment}",
                vpc_id=vpc.id,
                cidr_block=f"10.0.{i * 2 + 1}.0/24",
                availability_zone=az,
                tags={
                    **tags,
                    "Name": f"{app_name}-private-{az}",
                    "kubernetes.io/role/internal-elb": "1"
                }
            )
            private_subnets.append(private_subnet)

        resources["public_subnets"] = public_subnets
        resources["private_subnets"] = private_subnets

        # Internet Gateway
        igw = aws.ec2.InternetGateway(
            f"{app_name}-igw-{environment}",
            vpc_id=vpc.id,
            tags={**tags, "Name": f"{app_name}-igw-{environment}"}
        )
        resources["igw"] = igw

        # Route table for public subnets
        public_rt = aws.ec2.RouteTable(
            f"{app_name}-public-rt-{environment}",
            vpc_id=vpc.id,
            routes=[
                aws.ec2.RouteTableRouteArgs(
                    cidr_block="0.0.0.0/0",
                    gateway_id=igw.id
                )
            ],
            tags={**tags, "Name": f"{app_name}-public-rt-{environment}"}
        )

        for i, subnet in enumerate(public_subnets):
            aws.ec2.RouteTableAssociation(
                f"{app_name}-public-rta-{i}-{environment}",
                subnet_id=subnet.id,
                route_table_id=public_rt.id
            )

        # NAT Gateway for private subnets
        eip = aws.ec2.Eip(
            f"{app_name}-nat-eip-{environment}",
            domain="vpc",
            tags={**tags, "Name": f"{app_name}-nat-eip-{environment}"}
        )

        nat_gw = aws.ec2.NatGateway(
            f"{app_name}-nat-{environment}",
            subnet_id=public_subnets[0].id,
            allocation_id=eip.id,
            tags={**tags, "Name": f"{app_name}-nat-{environment}"}
        )
        resources["nat_gateway"] = nat_gw

        # Route table for private subnets
        private_rt = aws.ec2.RouteTable(
            f"{app_name}-private-rt-{environment}",
            vpc_id=vpc.id,
            routes=[
                aws.ec2.RouteTableRouteArgs(
                    cidr_block="0.0.0.0/0",
                    nat_gateway_id=nat_gw.id
                )
            ],
            tags={**tags, "Name": f"{app_name}-private-rt-{environment}"}
        )

        for i, subnet in enumerate(private_subnets):
            aws.ec2.RouteTableAssociation(
                f"{app_name}-private-rta-{i}-{environment}",
                subnet_id=subnet.id,
                route_table_id=private_rt.id
            )

        vpc_id = vpc.id
        subnet_ids = [s.id for s in public_subnets + private_subnets]

    # Create EKS Cluster
    cluster = eks.Cluster(
        f"{app_name}-eks-{environment}",
        name=f"{app_name}-{environment}",
        vpc_id=vpc_id if isinstance(vpc_id, str) else vpc.id,
        subnet_ids=subnet_ids if 'subnet_ids' in dir() else None,
        instance_type="t3.medium",
        desired_capacity=2,
        min_size=1,
        max_size=4,
        node_associate_public_ip_address=False,
        tags=tags
    )
    resources["eks_cluster"] = cluster

    # Create Kubernetes provider for the cluster
    k8s_provider = k8s.Provider(
        f"{app_name}-k8s-provider-{environment}",
        kubeconfig=cluster.kubeconfig
    )
    resources["k8s_provider"] = k8s_provider

    # Create monitoring namespace
    monitoring_ns = k8s.core.v1.Namespace(
        "monitoring",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="monitoring"
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider)
    )
    resources["monitoring_namespace"] = monitoring_ns

    # Deploy Prometheus using Helm
    prometheus = Chart(
        "prometheus",
        ChartOpts(
            chart="prometheus",
            version="25.8.0",
            namespace="monitoring",
            fetch_opts=FetchOpts(
                repo="https://prometheus-community.github.io/helm-charts"
            ),
            values={
                "server": {
                    "persistentVolume": {
                        "size": "10Gi"
                    },
                    "resources": {
                        "requests": {
                            "cpu": "250m",
                            "memory": "512Mi"
                        },
                        "limits": {
                            "cpu": "500m",
                            "memory": "1Gi"
                        }
                    }
                },
                "alertmanager": {
                    "enabled": True
                }
            }
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[monitoring_ns]
        )
    )
    resources["prometheus"] = prometheus

    # Deploy Grafana using Helm
    grafana = Chart(
        "grafana",
        ChartOpts(
            chart="grafana",
            version="7.0.0",
            namespace="monitoring",
            fetch_opts=FetchOpts(
                repo="https://grafana.github.io/helm-charts"
            ),
            values={
                "adminPassword": pulumi.Config().get_secret("grafanaAdminPassword") or "admin",
                "persistence": {
                    "enabled": True,
                    "size": "5Gi"
                },
                "service": {
                    "type": "LoadBalancer"
                },
                "datasources": {
                    "datasources.yaml": {
                        "apiVersion": 1,
                        "datasources": [
                            {
                                "name": "Prometheus",
                                "type": "prometheus",
                                "url": "http://prometheus-server.monitoring.svc.cluster.local",
                                "access": "proxy",
                                "isDefault": True
                            },
                            {
                                "name": "CloudWatch",
                                "type": "cloudwatch",
                                "jsonData": {
                                    "authType": "default",
                                    "defaultRegion": "us-west-2"
                                }
                            }
                        ]
                    }
                },
                "dashboardProviders": {
                    "dashboardproviders.yaml": {
                        "apiVersion": 1,
                        "providers": [
                            {
                                "name": "default",
                                "orgId": 1,
                                "folder": "",
                                "type": "file",
                                "disableDeletion": False,
                                "editable": True,
                                "options": {
                                    "path": "/var/lib/grafana/dashboards/default"
                                }
                            }
                        ]
                    }
                },
                "resources": {
                    "requests": {
                        "cpu": "100m",
                        "memory": "256Mi"
                    },
                    "limits": {
                        "cpu": "200m",
                        "memory": "512Mi"
                    }
                }
            }
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[monitoring_ns, prometheus]
        )
    )
    resources["grafana"] = grafana

    return resources


def create_api_gateway_monitoring(
    app_name: str,
    environment: str,
    api_gateway_id: pulumi.Output,
    tags: dict
):
    """
    Create CloudWatch dashboards and alarms for API Gateway monitoring.
    """

    # CloudWatch Dashboard for API Gateway
    dashboard = aws.cloudwatch.Dashboard(
        f"{app_name}-api-dashboard-{environment}",
        dashboard_name=f"{app_name}-api-{environment}",
        dashboard_body=api_gateway_id.apply(lambda api_id: f"""{{
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
        }}""")
    )

    # SNS Topic for alarms
    alarm_topic = aws.sns.Topic(
        f"{app_name}-alarm-topic-{environment}",
        name=f"{app_name}-alarms-{environment}",
        tags=tags
    )

    # High Error Rate Alarm
    error_alarm = aws.cloudwatch.MetricAlarm(
        f"{app_name}-high-error-rate-{environment}",
        alarm_name=f"{app_name}-high-error-rate-{environment}",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=2,
        metric_name="5XXError",
        namespace="AWS/ApiGateway",
        period=300,
        statistic="Sum",
        threshold=10,
        alarm_description="API Gateway 5XX errors exceeded threshold",
        dimensions={
            "ApiName": f"{app_name}-api-{environment}"
        },
        alarm_actions=[alarm_topic.arn],
        ok_actions=[alarm_topic.arn],
        tags=tags
    )

    # High Latency Alarm
    latency_alarm = aws.cloudwatch.MetricAlarm(
        f"{app_name}-high-latency-{environment}",
        alarm_name=f"{app_name}-high-latency-{environment}",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=3,
        metric_name="Latency",
        namespace="AWS/ApiGateway",
        period=300,
        statistic="Average",
        threshold=3000,  # 3 seconds
        alarm_description="API Gateway latency exceeded 3 seconds",
        dimensions={
            "ApiName": f"{app_name}-api-{environment}"
        },
        alarm_actions=[alarm_topic.arn],
        ok_actions=[alarm_topic.arn],
        tags=tags
    )

    return {
        "dashboard": dashboard,
        "alarm_topic": alarm_topic,
        "error_alarm": error_alarm,
        "latency_alarm": latency_alarm
    }

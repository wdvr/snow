# Grafana Dashboards for Snow Tracker

These dashboard JSON files can be imported into Amazon Managed Grafana to monitor the Snow Tracker application.

## Dashboards

### 1. Scraping Monitor (`scraping-monitor.json`)
Monitors the weather data scraping process:
- **Scraper Success Rate** - Percentage of successful scrapes
- **Resorts Processed** - Number of resorts processed per hour
- **Processing Errors** - Error count
- **Processing Duration** - How long each scrape run takes
- **Conditions Saved Over Time** - Weather conditions written to DynamoDB
- **Scraper Hits vs Misses** - OnTheSnow scraper success/failure
- **Lambda Invocations** - Weather processor Lambda execution stats

### 2. API Performance (`api-performance.json`)
Monitors API Gateway and Lambda performance:
- **Request Count** - API requests per 5 minutes
- **Average Latency** - Response time gauge
- **4XX/5XX Errors** - Client and server error counts
- **Latency Over Time** - Average and p95 latency
- **Lambda Duration** - API handler Lambda execution time

### 3. DynamoDB Metrics (`dynamodb-metrics.json`)
Monitors database performance:
- **Read/Write Capacity** - Consumed capacity units
- **Throttled Requests** - Requests that hit capacity limits
- **Request Latency** - DynamoDB operation latency
- **Item Count & Table Size** - Storage metrics

## How to Import

1. Open your Grafana workspace: https://g-XXXXX.grafana-workspace.us-west-2.amazonaws.com
2. Go to **Dashboards** → **Import**
3. Click **Upload JSON file** and select the dashboard file
4. Select your **CloudWatch** data source
5. Click **Import**

## Prerequisites

### CloudWatch Data Source
1. In Grafana, go to **Configuration** → **Data Sources**
2. Add **Amazon CloudWatch**
3. Configure with your AWS region (us-west-2)
4. Authentication should be automatic via IAM role

### Custom Metrics
The scraping dashboard requires custom CloudWatch metrics published by the weather processor Lambda. These metrics are in the `SnowTracker/Scraping` namespace:
- `ResortsProcessed`
- `ElevationPointsProcessed`
- `ConditionsSaved`
- `ScraperHits`
- `ScraperMisses`
- `ProcessingErrors`
- `ProcessingDuration`
- `ScraperSuccessRate`

## Environment Configuration

The dashboards are configured for `staging` environment. To monitor other environments:
1. After importing, edit the dashboard
2. Find dimension values like `snow-tracker-api-staging`
3. Change to `snow-tracker-api-prod` or `snow-tracker-api-dev`

Or create dashboard variables for environment switching.

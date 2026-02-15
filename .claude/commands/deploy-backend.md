# Deploy Snow Backend

The backend runs on AWS Lambda + DynamoDB, deployed via Pulumi.

## Via GitHub Actions (preferred)

```bash
# Deploy to staging
gh workflow run deploy --repo wdvr/snow -f environment=staging

# Deploy to production
gh workflow run deploy --repo wdvr/snow -f environment=production
```

## Via Pulumi (manual)

```bash
cd infrastructure
source ../venv/bin/activate
pip install -r requirements.txt

# Preview changes
AWS_PROFILE=personal pulumi preview --stack dev

# Deploy
AWS_PROFILE=personal pulumi up --yes --stack dev
```

## Trigger Weather Update

```bash
# Manual weather processing
gh workflow run trigger-weather --repo wdvr/snow -f environment=staging
```

## API Endpoints
- **Staging**: https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging
- **Production**: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod

## Notes
- AWS Region: us-west-2
- DynamoDB tables: snow-tracker-resorts-{env}, snow-tracker-weather-conditions-{env}, snow-tracker-user-preferences-{env}
- Weather Processor runs hourly via scheduled Lambda
- Daily scraper discovers new ski resorts (23 countries)
- Always use `AWS_PROFILE=personal`

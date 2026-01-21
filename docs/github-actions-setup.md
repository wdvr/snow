# GitHub Actions Setup Guide

This guide covers setting up GitHub Actions for the Snow Quality Tracker project, including AWS credentials configuration and testing pipeline setup.

## Required GitHub Secrets

To enable CI/CD and deployment, add these secrets to your GitHub repository:

### AWS Configuration

1. **AWS_ACCESS_KEY_ID**
   - Description: AWS Access Key for programmatic access
   - Source: AWS IAM User credentials (for `personal` profile)
   - Required for: Infrastructure deployment, Lambda deployment

2. **AWS_SECRET_ACCESS_KEY**
   - Description: AWS Secret Access Key
   - Source: AWS IAM User credentials (for `personal` profile)
   - Required for: Infrastructure deployment, Lambda deployment

### Pulumi Configuration

3. **PULUMI_CONFIG_PASSPHRASE**
   - Description: Encryption passphrase for Pulumi state
   - Value: Choose a strong passphrase (store securely)
   - Required for: Infrastructure deployment

### Third-Party API Keys

4. **WEATHER_API_KEY** (will be needed later)
   - Description: WeatherAPI.com API key
   - Source: Sign up at https://www.weatherapi.com/
   - Required for: Weather data fetching

## Setting Up AWS IAM User for GitHub Actions

### 1. Create IAM User

```bash
# Using AWS CLI with your personal profile
aws iam create-user --user-name github-actions-snow-tracker --profile personal
```

### 2. Create Access Keys

```bash
aws iam create-access-key --user-name github-actions-snow-tracker --profile personal
```

Save the Access Key ID and Secret Access Key for GitHub secrets.

### 3. Create IAM Policy

Create a policy file `github-actions-policy.json`:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:*",
                "lambda:*",
                "apigateway:*",
                "iam:*",
                "cloudwatch:*",
                "logs:*",
                "cognito-idp:*",
                "s3:*",
                "cloudformation:*"
            ],
            "Resource": "*"
        }
    ]
}
```

Attach the policy:

```bash
aws iam create-policy \
    --policy-name GitHubActionsSnowTracker \
    --policy-document file://github-actions-policy.json \
    --profile personal

aws iam attach-user-policy \
    --user-name github-actions-snow-tracker \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/GitHubActionsSnowTracker \
    --profile personal
```

## Adding Secrets to GitHub

### Via GitHub Web Interface

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret:

   - Name: `AWS_ACCESS_KEY_ID`
     Value: `[Access Key from step 2 above]`

   - Name: `AWS_SECRET_ACCESS_KEY`
     Value: `[Secret Key from step 2 above]`

   - Name: `PULUMI_CONFIG_PASSPHRASE`
     Value: `[Choose a strong passphrase]`

### Via GitHub CLI

```bash
# Set AWS credentials
gh secret set AWS_ACCESS_KEY_ID --body "AKIAIOSFODNN7EXAMPLE"
gh secret set AWS_SECRET_ACCESS_KEY --body "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE"

# Set Pulumi passphrase
gh secret set PULUMI_CONFIG_PASSPHRASE --body "your-strong-passphrase"
```

## Environment Setup

### Development Environment

For local development, create `.env` file:

```bash
cp .env.example .env
# Edit .env with your local AWS profile settings
```

### GitHub Actions Environments

The deployment workflow uses GitHub Environments for different stages:

1. **dev** - Development environment (auto-deploy)
2. **staging** - Staging environment (manual approval)
3. **prod** - Production environment (manual approval + protection rules)

To set up environments:

1. Go to **Settings** → **Environments**
2. Create environments: `dev`, `staging`, `prod`
3. For `staging` and `prod`:
   - Enable "Required reviewers"
   - Add protection rules as needed

## Workflow Overview

### CI Pipeline (`.github/workflows/ci.yml`)

Triggers on:
- Push to `main` or `develop`
- Pull requests to `main` or `develop`

Jobs:
1. **Backend Tests** - Unit and integration tests with coverage
2. **Infrastructure Validation** - Pulumi configuration validation
3. **Code Quality** - Linting, formatting, security scanning
4. **Test Summary** - Aggregate results

### Deployment Pipeline (`.github/workflows/deploy.yml`)

Triggers on:
- Push to `main` (deploys to dev)
- Manual trigger (choose environment)

Jobs:
1. **Deploy Infrastructure** - Pulumi deployment
2. **Package Lambda** - Create deployment package
3. **Seed Data** - Populate initial resort data (dev only)
4. **Smoke Tests** - Basic API validation

## Testing the Setup

### 1. Test CI Pipeline

Create a simple change and push to trigger CI:

```bash
git checkout -b test-ci
echo "# Test CI" >> README.md
git add README.md
git commit -m "Test CI pipeline"
git push -u origin test-ci
```

Create a PR and verify all checks pass.

### 2. Test Deployment

After merging to `main`, check the deployment workflow:

1. Go to **Actions** tab
2. Find "Deploy to AWS" workflow
3. Verify deployment to `dev` environment succeeds

### 3. Verify Infrastructure

Check that AWS resources are created:

```bash
# List DynamoDB tables
aws dynamodb list-tables --region us-west-2 --profile personal

# Check API Gateway
aws apigateway get-rest-apis --region us-west-2 --profile personal

# Check Lambda functions
aws lambda list-functions --region us-west-2 --profile personal
```

## Troubleshooting

### Common Issues

1. **Permission Denied Errors**
   - Verify IAM user has required permissions
   - Check AWS credentials in GitHub secrets

2. **Pulumi State Issues**
   - Ensure `PULUMI_CONFIG_PASSPHRASE` is set correctly
   - Check Pulumi backend configuration

3. **Test Failures**
   - Review test logs in GitHub Actions
   - Run tests locally to debug: `cd backend && pytest tests/ -v`

4. **Deployment Failures**
   - Check AWS CloudFormation console for detailed errors
   - Verify resource limits haven't been exceeded

### Getting Help

- Check GitHub Actions logs for detailed error messages
- Review AWS CloudWatch logs for runtime issues
- Consult Pulumi documentation for infrastructure problems

## Security Best Practices

1. **Least Privilege**: Grant minimal required permissions to IAM user
2. **Rotate Keys**: Regularly rotate AWS access keys
3. **Environment Separation**: Use different AWS accounts for prod if possible
4. **Secret Management**: Never commit secrets to code
5. **Review Access**: Regularly audit who has access to GitHub repository

## Next Steps

After setup is complete:

1. Configure WeatherAPI.com account and add API key
2. Test full deployment pipeline
3. Set up monitoring and alerting
4. Configure branch protection rules
5. Set up code quality gates
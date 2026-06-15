# Deployment Guide - BidPilot AI

## Production Checklist

- [ ] Database backups configured
- [ ] SSL/TLS certificates installed
- [ ] Environment variables set
- [ ] S3 bucket created and access verified
- [ ] OpenAI API key validated
- [ ] Razorpay sandbox tested
- [ ] Email SMTP configured
- [ ] Monitoring & alerting set up
- [ ] Uptime monitoring configured
- [ ] Backup & disaster recovery tested

## Render.com Deployment (Recommended)

### Backend

1. Create Render account
2. Connect GitHub repo
3. Create new "Web Service"
4. Build: `pip install -r backend/requirements.txt`
5. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Environment variables:
   - DATABASE_URL: (PostgreSQL addon)
   - REDIS_URL: (Redis addon)
   - QDRANT_URL: (self-hosted or Qdrant Cloud)
   - OPENAI_API_KEY
   - AWS credentials
   - RAZORPAY keys

### Celery Worker

1. Create another web service
2. Build: (same as backend)
3. Start: `celery -A app.jobs.celery_config worker -l info`
4. Set to "Private Service" (no public URL)

### Frontend

Deploy to Vercel:
1. Connect GitHub
2. Framework: Next.js
3. Environment: NEXT_PUBLIC_API_URL=https://your-backend.onrender.com

## AWS Deployment

### EC2 + RDS + ElastiCache

```bash
# Launch EC2 instance (Ubuntu 22.04)
ssh -i key.pem ubuntu@instance-ip

# Install Docker
curl -sSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu

# Clone repo & setup
git clone <repo>
cd bidpilot-saas
cp .env.example .env
# Edit .env with RDS endpoint, ElastiCache endpoint

# Start
docker-compose up -d
```

### RDS PostgreSQL
- Version: 15
- Instance: db.t3.micro (production: db.t4g.small)
- Storage: 100GB gp3
- Backup retention: 7 days
- Multi-AZ: enabled

### ElastiCache Redis
- Engine: 7.0
- Node type: cache.t4g.micro
- Num cache nodes: 3
- Multi-AZ: enabled

### S3 Bucket
```bash
aws s3 mb s3://bidpilot-production --region us-east-1
aws s3api put-bucket-versioning --bucket bidpilot-production --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket bidpilot-production \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

### CloudFront (Optional, for faster S3 access)
- Origin: S3 bucket
- Compress: enabled
- Cache policy: Managed-CachingOptimized

## Kubernetes Deployment

```bash
# Create namespace
kubectl create namespace bidpilot

# Create secrets
kubectl create secret generic db-secret \
  --from-literal=password=<db_password> \
  -n bidpilot

# Deploy
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl apply -f k8s/redis-statefulset.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml

# Expose
kubectl expose deployment backend -n bidpilot --type=LoadBalancer --port=80 --target-port=8000
```

## Monitoring & Logging

### Sentry (Error Tracking)
```python
# In config.py
SENTRY_DSN = "https://xxx@sentry.io/xxx"

import sentry_sdk
sentry_sdk.init(dsn=settings.SENTRY_DSN)
```

### CloudWatch Logs (AWS)
```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
```

### Datadog (Optional)
- Install agent
- Connect logs, metrics, traces

## Backup & Recovery

### Daily Database Backups
```bash
# Automated via RDS
# Manual backup:
pg_dump -h <rds-endpoint> -U bidpilot bidpilot > backup.sql

# Restore:
psql -h <new-host> -U bidpilot bidpilot < backup.sql
```

### S3 Backup Policy
- Versioning: enabled
- Cross-region replication: enabled
- Lifecycle policy: delete versions after 30 days

## Security

### SSL/TLS
```bash
# Use ACM certificate (AWS)
# Or LetsEncrypt for self-hosted
```

### Firewall Rules
- Backend: Allow only from frontend domain
- Database: Allow only from backend
- Redis: Allow only from backend + worker

### Secrets Management
- AWS Secrets Manager
- Don't commit .env to git
- Rotate keys every 90 days

## Performance Tuning

### Database
```sql
-- Create indexes
CREATE INDEX idx_tender_org_id ON tenders(organization_id);
CREATE INDEX idx_tender_status ON tenders(status);
CREATE INDEX idx_user_org_id ON users(organization_id);

-- Monitor slow queries
ALTER SYSTEM SET log_min_duration_statement = 1000;
```

### Redis
```bash
# Monitor
redis-cli MONITOR

# Check memory
redis-cli INFO memory
```

### Application
```python
# Enable caching
from functools import lru_cache

@lru_cache(maxsize=1000)
def expensive_function():
    pass
```

## Disaster Recovery

1. **RTO (Recovery Time Objective)**: < 1 hour
2. **RPO (Recovery Point Objective)**: < 15 minutes

### Plan
- Daily automated backups
- Weekly full backups to cold storage (S3 Glacier)
- Test recovery monthly
- Document all procedures

## Cost Estimation (Monthly)

| Service | Cost |
|---------|------|
| Render PostgreSQL | $35 |
| Render Redis | $35 |
| Render Backend | $7 |
| Render Worker | $7 |
| Vercel Frontend | Free |
| S3 Storage (100GB) | $2.50 |
| S3 Data Transfer | $5 |
| OpenAI API | $50-200 |
| Razorpay (1% + ₹0) | Variable |
| **Total** | **~$140-300** |


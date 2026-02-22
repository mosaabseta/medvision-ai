# GI Copilot - Deployment Guide

## Quick Start with Docker Compose

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- NVIDIA GPU (for AI inference)
- 16GB+ RAM
- 100GB+ storage

### 1. Clone Repository
```bash
git clone https://github.com/yourorg/gi-copilot.git
cd gi-copilot
```

### 2. Configure Environment
```bash
cp .env.template .env
nano .env  # Edit with your configuration
```

Required configuration:
- `SECRET_KEY`: Generate with `openssl rand -hex 32`
- `OPENAI_API_KEY`: Your OpenAI API key
- `DB_PASSWORD`: PostgreSQL password

### 3. Start Services
```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

### 4. Initialize Database
```bash
# Run migrations
docker-compose exec api alembic upgrade head

# Create admin user (optional)
docker-compose exec api python scripts/create_admin.py
```

### 5. Access Application
- API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs
- Flower (Celery Monitor): http://localhost:5555
- MinIO Console: http://localhost:9001

---

## Production Deployment

### Option 1: AWS Deployment

#### Architecture
```
Internet
   ↓
Application Load Balancer
   ↓
ECS Fargate (API Containers)
   ↓
├── RDS PostgreSQL
├── ElastiCache Redis
├── S3 (Video Storage)
└── ECS Fargate (Worker Containers with GPU)
```

#### Steps

1. **Setup Infrastructure**
```bash
# Install Terraform
brew install terraform  # macOS
# or apt-get install terraform  # Linux

# Initialize Terraform
cd terraform/aws
terraform init
terraform plan
terraform apply
```

2. **Build and Push Docker Images**
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t gi-copilot-api -f Dockerfile_production .
docker tag gi-copilot-api:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/gi-copilot-api:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/gi-copilot-api:latest
```

3. **Deploy with ECS**
```bash
# Update ECS service
aws ecs update-service --cluster gi-copilot --service api --force-new-deployment
```

#### AWS Resources Created
- VPC with public/private subnets
- Application Load Balancer
- ECS Cluster with Fargate tasks
- RDS PostgreSQL (Multi-AZ)
- ElastiCache Redis
- S3 bucket with lifecycle policies
- CloudWatch logs
- IAM roles and security groups

### Option 2: Kubernetes Deployment

#### Prerequisites
- Kubernetes 1.24+
- kubectl configured
- Helm 3.0+
- NGINX Ingress Controller
- cert-manager (for TLS)

#### Steps

1. **Create Namespace**
```bash
kubectl create namespace gi-copilot
```

2. **Install Dependencies**
```bash
# PostgreSQL
helm install postgres bitnami/postgresql \
  --namespace gi-copilot \
  --set auth.database=gi_copilot \
  --set auth.password=<password>

# Redis
helm install redis bitnami/redis \
  --namespace gi-copilot \
  --set auth.enabled=false

# MinIO
helm install minio bitnami/minio \
  --namespace gi-copilot \
  --set auth.rootUser=admin \
  --set auth.rootPassword=<password>
```

3. **Deploy Application**
```bash
cd kubernetes

# Create ConfigMap
kubectl apply -f configmap.yaml -n gi-copilot

# Create Secrets
kubectl create secret generic gi-copilot-secrets \
  --from-literal=secret-key=<secret-key> \
  --from-literal=openai-api-key=<api-key> \
  -n gi-copilot

# Deploy API
kubectl apply -f api-deployment.yaml -n gi-copilot

# Deploy Workers
kubectl apply -f worker-deployment.yaml -n gi-copilot

# Create Services
kubectl apply -f services.yaml -n gi-copilot

# Create Ingress
kubectl apply -f ingress.yaml -n gi-copilot
```

4. **Verify Deployment**
```bash
kubectl get pods -n gi-copilot
kubectl logs -f deployment/gi-copilot-api -n gi-copilot
```

---

## Scaling Strategies

### Horizontal Scaling

#### API Tier
```bash
# Docker Compose
docker-compose up -d --scale api=3

# Kubernetes
kubectl scale deployment gi-copilot-api --replicas=5 -n gi-copilot
```

#### Worker Tier
```bash
# Scale workers based on queue depth
# Kubernetes HPA
kubectl apply -f hpa-worker.yaml
```

### Vertical Scaling

#### Increase Resources
```yaml
# Kubernetes
resources:
  requests:
    memory: "8Gi"
    cpu: "4"
    nvidia.com/gpu: "1"
  limits:
    memory: "16Gi"
    cpu: "8"
    nvidia.com/gpu: "1"
```

---

## Monitoring & Observability

### Prometheus + Grafana

1. **Install Prometheus Stack**
```bash
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring
```

2. **Import Dashboards**
- API metrics: `/monitoring/dashboards/api.json`
- Worker metrics: `/monitoring/dashboards/workers.json`
- Database metrics: `/monitoring/dashboards/postgres.json`

3. **Configure Alerts**
```bash
kubectl apply -f monitoring/alerts.yaml
```

### Logging with ELK Stack

1. **Deploy Elasticsearch**
```bash
helm install elasticsearch elastic/elasticsearch -n logging
```

2. **Deploy Logstash**
```bash
kubectl apply -f logging/logstash-config.yaml
```

3. **Deploy Kibana**
```bash
helm install kibana elastic/kibana -n logging
```

---

## Backup & Disaster Recovery

### Database Backups

#### Automated Daily Backups
```bash
# PostgreSQL backup to S3
0 2 * * * pg_dump -h postgres -U gi_copilot gi_copilot | gzip | aws s3 cp - s3://gi-copilot-backups/db/$(date +\%Y-\%m-\%d).sql.gz
```

#### Restore from Backup
```bash
aws s3 cp s3://gi-copilot-backups/db/2024-02-11.sql.gz - | gunzip | psql -h postgres -U gi_copilot gi_copilot
```

### Video Storage Backups

#### S3 Cross-Region Replication
```bash
aws s3api put-bucket-replication --bucket gi-copilot \
  --replication-configuration file://replication-config.json
```

### Disaster Recovery Plan

1. **Recovery Time Objective (RTO)**: 4 hours
2. **Recovery Point Objective (RPO)**: 1 hour

**Steps:**
1. Deploy infrastructure in DR region
2. Restore database from latest backup
3. Update DNS to point to DR region
4. Sync S3 data
5. Verify all services operational

---

## Security Hardening

### 1. Network Security
```bash
# Restrict database access
# PostgreSQL: Only allow from API/Worker subnets
# Redis: Bind to localhost or private network
# MinIO: Use VPC endpoints
```

### 2. Secrets Management
```bash
# Use AWS Secrets Manager or HashiCorp Vault
aws secretsmanager create-secret \
  --name gi-copilot/openai-key \
  --secret-string "<api-key>"
```

### 3. Enable TLS/SSL
```yaml
# Ingress with TLS
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.gi-copilot.com
    secretName: gi-copilot-tls
```

### 4. Rate Limiting
```python
# Add to main_app.py
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.on_event("startup")
async def startup():
    await FastAPILimiter.init(redis_url)
```

---

## Performance Tuning

### Database Optimization

```sql
-- Create indexes
CREATE INDEX CONCURRENTLY idx_frames_session_timestamp 
ON video_frames(session_id, timestamp_ms);

CREATE INDEX CONCURRENTLY idx_analysis_risk_confidence 
ON frame_analysis(risk_level, confidence_score);

-- Analyze tables
ANALYZE video_sessions;
ANALYZE frame_analysis;
```

### Redis Configuration

```conf
# redis.conf
maxmemory 4gb
maxmemory-policy allkeys-lru
save ""
appendonly yes
```

### Worker Optimization

```python
# Celery configuration
CELERYD_PREFETCH_MULTIPLIER = 1
CELERYD_MAX_TASKS_PER_CHILD = 10
CELERY_ACKS_LATE = True
```

---

## Troubleshooting

### Common Issues

#### 1. Worker Not Processing Tasks
```bash
# Check Celery worker status
docker-compose logs celery_worker

# Check Redis connection
redis-cli -h redis ping

# Restart worker
docker-compose restart celery_worker
```

#### 2. Out of Memory Errors
```bash
# Increase container memory
docker update --memory 8g gi_copilot_celery_worker

# Or in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8G
```

#### 3. Slow Video Processing
```bash
# Reduce batch size
export BATCH_SIZE=5

# Increase worker concurrency
celery -A tasks worker --concurrency=4
```

#### 4. Database Connection Pool Exhausted
```python
# Increase pool size in database.py
engine = create_engine(
    DATABASE_URL,
    pool_size=20,  # Increase from 10
    max_overflow=40  # Increase from 20
)
```

---

## Maintenance

### Regular Tasks

#### Weekly
- Review error logs
- Check disk usage
- Verify backups
- Update security patches

#### Monthly
- Rotate logs
- Vacuum database
- Review performance metrics
- Update dependencies

#### Quarterly
- Disaster recovery drill
- Security audit
- Capacity planning review

### Update Procedure

```bash
# 1. Backup database
pg_dump gi_copilot > backup_$(date +%Y%m%d).sql

# 2. Pull latest code
git pull origin main

# 3. Update dependencies
pip install -r requirements_production.txt

# 4. Run migrations
alembic upgrade head

# 5. Restart services
docker-compose down
docker-compose up -d

# 6. Verify health
curl http://localhost:8000/health
```

---

## Support & Resources

- **Documentation**: https://docs.gi-copilot.com
- **API Reference**: https://api.gi-copilot.com/docs
- **GitHub Issues**: https://github.com/yourorg/gi-copilot/issues
- **Email**: support@gi-copilot.com

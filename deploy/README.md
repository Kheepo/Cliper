# Cliper Production Deployment Guide

This directory contains all the necessary configuration files, scripts, and documentation for deploying Cliper to production environments.

## 📁 Directory Structure

```
deploy/
├── config/                     # Environment configurations
│   ├── docker-compose.prod.yml # Production Docker Compose
│   ├── production.env          # Production environment variables
│   ├── staging.env             # Staging environment variables
│   └── nginx.conf              # Nginx configuration
├── monitoring/                 # Monitoring configurations
│   ├── prometheus.yml          # Prometheus configuration
│   ├── alertmanager.yml        # Alertmanager rules
│   └── grafana-dashboard.json  # Grafana dashboard
├── logging/                    # Logging configurations
│   ├── logstash.conf          # Logstash configuration
│   ├── elasticsearch-template.json # Elasticsearch template
│   └── filebeat.yml           # Filebeat configuration
├── scripts/                    # Deployment scripts
│   ├── deploy.sh              # Main deployment script
│   ├── backup.sh              # Backup script
│   └── restore.sh             # Restore script
└── README.md                  # This file
```

## 🚀 Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git
- Bash shell
- At least 8GB RAM and 50GB disk space
- SSL certificates for HTTPS

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/your-org/cliper.git
cd cliper/deploy

# Copy and configure environment files
cp config/production.env.example config/production.env
cp config/staging.env.example config/staging.env

# Edit environment files with your actual values
vim config/production.env
vim config/staging.env
```

### 2. SSL Certificate Setup

```bash
# Create SSL directory
sudo mkdir -p /etc/ssl/certs /etc/ssl/private

# Copy your SSL certificates
sudo cp your-domain.crt /etc/ssl/certs/cliper.crt
sudo cp your-domain.key /etc/ssl/private/cliper.key
sudo chmod 600 /etc/ssl/private/cliper.key
```

### 3. Deploy to Staging

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Deploy to staging
./scripts/deploy.sh staging --backup
```

### 4. Deploy to Production

```bash
# Deploy to production (with confirmation)
./scripts/deploy.sh production --backup

# Or force deploy without confirmation
./scripts/deploy.sh production --force --backup
```

## 🔧 Configuration

### Environment Variables

Key environment variables that must be configured:

#### Security
- `SECRET_KEY`: Application secret key
- `JWT_SECRET_KEY`: JWT signing key
- `POSTGRES_PASSWORD`: Database password
- `REDIS_PASSWORD`: Redis password

#### External Services
- `OPENAI_API_KEY`: OpenAI API key for AI features
- `STRIPE_SECRET_KEY`: Stripe secret key for payments
- `SMTP_PASSWORD`: Email server password
- `SLACK_WEBHOOK_URL`: Slack webhook for notifications

#### Storage
- `AWS_ACCESS_KEY_ID`: AWS access key for S3 storage
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `AWS_S3_BUCKET`: S3 bucket name

### Docker Compose Services

#### Core Services
- **nginx**: Reverse proxy and load balancer
- **frontend**: React frontend application
- **backend**: FastAPI backend application
- **worker**: Celery worker for background tasks
- **scheduler**: Celery beat scheduler
- **postgres**: PostgreSQL database
- **redis**: Redis cache and message broker

#### Monitoring Stack
- **prometheus**: Metrics collection
- **grafana**: Metrics visualization
- **alertmanager**: Alert management
- **node-exporter**: System metrics
- **cadvisor**: Container metrics

#### Logging Stack
- **elasticsearch**: Log storage and search
- **logstash**: Log processing
- **kibana**: Log visualization
- **filebeat**: Log shipping

#### Backup
- **backup**: Automated backup service

## 📊 Monitoring

### Grafana Dashboards

Access Grafana at `https://your-domain:3000`

Default credentials:
- Username: `admin`
- Password: Set in environment variables

### Prometheus Metrics

Access Prometheus at `https://your-domain:9090`

Key metrics monitored:
- HTTP request rates and latencies
- Database connection pools
- Redis performance
- System resources (CPU, memory, disk)
- Application-specific metrics

### Alerting

Alerts are configured for:
- High error rates
- High response times
- Resource exhaustion
- Service downtime
- Failed backups

## 📝 Logging

### Elasticsearch and Kibana

Access Kibana at `https://your-domain:5601`

Logs are automatically collected from:
- Application logs
- Nginx access/error logs
- System logs
- Container logs

### Log Levels

- **ERROR**: Application errors and exceptions
- **WARN**: Warning conditions
- **INFO**: General information
- **DEBUG**: Detailed debug information (staging only)

## 🔒 Security

### Security Headers

Nginx is configured with security headers:
- HSTS (HTTP Strict Transport Security)
- CSP (Content Security Policy)
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection

### Rate Limiting

API rate limiting is configured:
- 60 requests per minute per IP
- 1000 requests per hour per IP
- 10000 requests per day per IP

### SSL/TLS

- TLS 1.2 and 1.3 only
- Strong cipher suites
- HSTS enabled
- Certificate validation

## 💾 Backup and Recovery

### Automated Backups

Backups run daily at 2 AM and include:
- PostgreSQL database dump
- Redis data
- Uploaded media files
- Configuration files
- Application logs

### Manual Backup

```bash
# Create immediate backup
./scripts/backup.sh
```

### Restore from Backup

```bash
# List available backups
./scripts/restore.sh --list

# Restore specific backup
./scripts/restore.sh --restore backup_20240101_020000.tar.gz
```

### Backup Storage

- Local storage: `/opt/cliper/backups`
- Cloud storage: AWS S3 (configurable)
- Retention: 30 days (configurable)
- Encryption: AES-256 (optional)

## 🔄 Deployment Strategies

### Rolling Deployment

Default deployment strategy with zero downtime:

1. Build new Docker images
2. Create backup (if requested)
3. Deploy infrastructure services
4. Deploy application services
5. Run database migrations
6. Perform health checks
7. Update load balancer

### Blue-Green Deployment

For critical updates:

```bash
# Deploy to green environment
./scripts/deploy.sh production --environment=green

# Switch traffic to green
./scripts/switch-traffic.sh green

# Rollback if needed
./scripts/switch-traffic.sh blue
```

### Rollback

```bash
# Rollback to previous version
./scripts/deploy.sh production --rollback v1.2.3
```

## 🧪 Testing

### Health Checks

```bash
# Check all services
./scripts/deploy.sh --health-check

# Check specific service
curl https://your-domain/health
curl https://your-domain/health/ready
curl https://your-domain/health/live
```

### Load Testing

```bash
# Run load tests
cd ../tests/performance
locust -f load_test.py --host=https://staging.cliper.example.com
```

### Integration Tests

```bash
# Run integration tests
cd ../tests/integration
python -m pytest test_api_endpoints.py -v
```

## 🚨 Troubleshooting

### Common Issues

#### Service Won't Start

```bash
# Check service logs
docker-compose -f config/docker-compose.prod.yml logs backend

# Check service status
docker-compose -f config/docker-compose.prod.yml ps

# Restart specific service
docker-compose -f config/docker-compose.prod.yml restart backend
```

#### Database Connection Issues

```bash
# Check PostgreSQL logs
docker-compose -f config/docker-compose.prod.yml logs postgres

# Test database connection
docker-compose -f config/docker-compose.prod.yml exec postgres \
  psql -U cliper_user -d cliper_prod -c "SELECT 1;"
```

#### High Memory Usage

```bash
# Check container resource usage
docker stats

# Check system resources
free -h
df -h
```

#### SSL Certificate Issues

```bash
# Check certificate validity
openssl x509 -in /etc/ssl/certs/cliper.crt -text -noout

# Test SSL connection
openssl s_client -connect your-domain:443
```

### Log Analysis

```bash
# View application logs
docker-compose -f config/docker-compose.prod.yml logs -f backend

# View Nginx logs
docker-compose -f config/docker-compose.prod.yml logs -f nginx

# Search logs in Elasticsearch
curl -X GET "elasticsearch:9200/cliper-logs/_search?q=level:ERROR"
```

### Performance Issues

```bash
# Check Prometheus metrics
curl http://localhost:9090/api/v1/query?query=http_requests_total

# Check database performance
docker-compose -f config/docker-compose.prod.yml exec postgres \
  psql -U cliper_user -d cliper_prod -c "SELECT * FROM pg_stat_activity;"
```

## 📈 Scaling

### Horizontal Scaling

```bash
# Scale backend services
docker-compose -f config/docker-compose.prod.yml up -d --scale backend=3

# Scale worker services
docker-compose -f config/docker-compose.prod.yml up -d --scale worker=5
```

### Database Scaling

- Read replicas for PostgreSQL
- Redis clustering
- Connection pooling optimization

### Load Balancing

- Nginx upstream configuration
- Health check endpoints
- Session affinity (if needed)

## 🔧 Maintenance

### Regular Maintenance Tasks

1. **Weekly**:
   - Review monitoring alerts
   - Check backup integrity
   - Update security patches

2. **Monthly**:
   - Rotate logs
   - Clean up old Docker images
   - Review performance metrics

3. **Quarterly**:
   - Update dependencies
   - Security audit
   - Disaster recovery testing

### Maintenance Mode

```bash
# Enable maintenance mode
export MAINTENANCE_MODE=true
docker-compose -f config/docker-compose.prod.yml restart nginx

# Disable maintenance mode
export MAINTENANCE_MODE=false
docker-compose -f config/docker-compose.prod.yml restart nginx
```

## 📞 Support

### Emergency Contacts

- **DevOps Team**: devops@cliper.example.com
- **On-call Engineer**: +1-555-0123
- **Slack Channel**: #production-alerts

### Documentation

- [API Documentation](../docs/api.md)
- [Architecture Guide](../docs/architecture.md)
- [Security Guide](../docs/security.md)
- [Monitoring Guide](../docs/monitoring.md)

### External Resources

- [Docker Documentation](https://docs.docker.com/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

---

## 📄 License

This deployment configuration is part of the Cliper project and is licensed under the MIT License.

## 🤝 Contributing

For deployment-related improvements:

1. Fork the repository
2. Create a feature branch
3. Test changes in staging
4. Submit a pull request
5. Get approval from DevOps team

---

**Last Updated**: January 2024
**Version**: 1.0.0
**Maintainer**: DevOps Team <devops@cliper.example.com>
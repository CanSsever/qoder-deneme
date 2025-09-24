# 🚀 GA Launch Checklist & Runbook

This document provides the complete checklist and procedures for OneShot API GA (General Availability) launch.

## 📋 Pre-Launch Checklist

### 🔐 1. Security & Configuration

#### Production Configuration
- [ ] **Disable Safe Mode**: Set `SAFE_MODE=false` in production environment
- [ ] **Disable API Documentation**: Set `ENABLE_DOCS=false` 
- [ ] **Disable Debug Mode**: Set `ENABLE_DEBUG=false`
- [ ] **Force HTTPS**: Set `FORCE_HTTPS=true`
- [ ] **Secure Cookies**: Set `SECURE_COOKIES=true`
- [ ] **Enforce Real Providers**: Set `ENFORCE_REAL_PROVIDERS=true`

#### Secret Rotation (CRITICAL)
- [ ] **JWT Secret**: Generate and set new 32+ character JWT_SECRET
- [ ] **HMAC Secret**: Generate and set new HMAC_SECRET for webhooks
- [ ] **Database Password**: Rotate database credentials
- [ ] **Redis Password**: Set Redis AUTH password
- [ ] **S3/R2 Keys**: Rotate storage access keys
- [ ] **Superwall Keys**: Configure production Superwall secrets
- [ ] **Sentry DSN**: Set production Sentry project DSN

#### Domain Configuration
- [ ] **Replace Placeholder Domains**: Update all `yourdomain.com` references
- [ ] **DNS Configuration**: Configure production DNS A/AAAA records
- [ ] **SSL Certificates**: Verify Cloudflare SSL/ACME configuration
- [ ] **CORS Origins**: Set strict production CORS allowed origins

### 🛡️ 2. Security Hardening

#### Traefik Security
- [ ] **CORS Restrictions**: Only allow production app domains
- [ ] **HTTPS Enforcement**: All HTTP redirects to HTTPS
- [ ] **HSTS Headers**: 1-year max-age with subdomains and preload
- [ ] **Security Headers**: CSP, X-Frame-Options, XSS Protection enabled
- [ ] **TLS Configuration**: TLS 1.3 preferred, modern cipher suites
- [ ] **Rate Limiting**: Production-appropriate rate limits configured

#### Application Security
- [ ] **Authentication**: JWT validation working
- [ ] **Authorization**: Role-based access controls active
- [ ] **Input Validation**: All API endpoints validated
- [ ] **Error Handling**: No sensitive data in error responses

### 🗄️ 3. Database & Storage

#### Database Setup
- [ ] **Production Database**: PostgreSQL configured and accessible
- [ ] **Connection Pool**: Appropriate connection limits set
- [ ] **Migrations**: All migrations applied successfully
- [ ] **Backup Strategy**: Daily automated backups configured
- [ ] **Retention Policy**: Data retention cleanup scheduled

#### Storage Configuration
- [ ] **R2/S3 Bucket**: Production storage bucket configured
- [ ] **Access Policies**: Least-privilege access controls
- [ ] **Lifecycle Rules**: Automated storage class transitions
- [ ] **Backup Verification**: Storage backup strategy tested

### 🔧 4. Infrastructure

#### Container & Orchestration
- [ ] **Docker Images**: Production images built and tagged
- [ ] **Resource Limits**: CPU/memory limits appropriate for production
- [ ] **Health Checks**: Container health checks configured
- [ ] **Restart Policies**: Automatic restart on failure

#### Networking
- [ ] **Load Balancer**: Production load balancer configured
- [ ] **SSL Termination**: SSL/TLS termination at load balancer
- [ ] **Firewall Rules**: Only necessary ports exposed
- [ ] **CDN Configuration**: Static asset delivery optimized

### 📊 5. Monitoring & Observability

#### Metrics & Alerts
- [ ] **Prometheus**: Metrics collection active
- [ ] **Grafana**: Dashboards configured and accessible
- [ ] **Alertmanager**: Alert rules configured
- [ ] **Sentry**: Error tracking and performance monitoring
- [ ] **Log Aggregation**: Centralized logging configured

#### Alert Thresholds
- [ ] **Error Rate**: > 5% error rate alerts
- [ ] **Response Time**: > 2s P95 latency alerts
- [ ] **Resource Usage**: > 80% CPU/memory alerts
- [ ] **Disk Space**: > 90% disk usage alerts
- [ ] **Certificate Expiry**: 30-day certificate expiry warning

## 🚀 Launch Procedures

### Phase 1: Final Preparation (T-24h)

1. **Run Production Validation**
   ```bash
   make validate:prod
   python scripts/validate-prod-config.py
   ```

2. **Verify Backup Systems**
   ```bash
   bash scripts/verify-backups.py
   bash scripts/verify-retention.sh
   ```

3. **Security Scan**
   ```bash
   make security:scan
   ```

4. **Load Testing** (if applicable)
   ```bash
   make load-test:production
   ```

### Phase 2: Canary Deployment (T-2h)

1. **Deploy Canary (10%)**
   ```bash
   bash scripts/canary-deploy.sh oneshot:v1.0.0
   ```

2. **Monitor Canary (5 minutes)**
   - Error rate < 5%
   - P95 latency < 2s
   - Health checks passing

3. **Smoke Test Canary**
   ```bash
   make smoke:prod:bail
   ```

### Phase 3: Full Deployment (T-0h)

1. **Promote Canary to 100%**
   - Canary will auto-promote if metrics are healthy
   - Manual promotion if needed

2. **Run Full Smoke Tests**
   ```bash
   make smoke:prod
   ```

3. **Verify All Services**
   ```bash
   make health:check:all
   ```

### Phase 4: Post-Launch Validation (T+30m)

1. **Monitor Key Metrics**
   - Response times
   - Error rates
   - Resource utilization
   - User authentication

2. **Run Extended Tests**
   ```bash
   make test:e2e:production
   ```

3. **Validate Integrations**
   - Payment processing
   - AI providers
   - Storage uploads
   - Webhook delivery

## 🔄 Rollback Procedures

### Automatic Rollback Triggers
- Error rate > 5% for 2 minutes
- P95 latency > 2s for 2 minutes
- Health check failures > 3 consecutive
- Manual trigger via monitoring alert

### Manual Rollback Process

1. **Immediate Rollback**
   ```bash
   bash scripts/rollback.sh
   ```

2. **Verify Rollback**
   ```bash
   make smoke:prod:bail
   ```

3. **Investigate Issues**
   - Check application logs
   - Review error tracking
   - Analyze performance metrics

### Emergency Contact Procedures
- Slack: #production-alerts
- PagerDuty: Production escalation
- Email: oncall@yourdomain.com

## 📝 Post-Launch Tasks

### Immediate (T+1h)
- [ ] Confirm all monitoring alerts are working
- [ ] Verify backup jobs are running
- [ ] Check data retention cleanup
- [ ] Monitor user feedback channels

### First Day (T+24h)
- [ ] Review launch metrics and performance
- [ ] Analyze error logs and patterns
- [ ] Verify billing and payment processing
- [ ] Check storage usage and costs

### First Week (T+7d)
- [ ] Performance optimization review
- [ ] Cost analysis and optimization
- [ ] User feedback analysis
- [ ] Security posture review

## 🛠️ Maintenance Procedures

### Daily Operations
- [ ] Monitor dashboard review
- [ ] Error log analysis
- [ ] Performance metrics check
- [ ] Backup verification

### Weekly Operations
- [ ] Security updates
- [ ] Dependency updates
- [ ] Performance optimization
- [ ] Cost optimization review

### Monthly Operations
- [ ] Full security audit
- [ ] Disaster recovery test
- [ ] Capacity planning review
- [ ] Business metrics analysis

## 📞 Emergency Contacts

### Technical Team
- **DevOps Lead**: oncall@yourdomain.com
- **Security Team**: security@yourdomain.com
- **Database Admin**: dba@yourdomain.com

### Business Contacts
- **Product Manager**: product@yourdomain.com
- **Customer Support**: support@yourdomain.com

## 📚 Reference Documentation

### Internal Documentation
- [Security Configuration](deploy/production/SECURITY-CONFIG.md)
- [Monitoring Runbook](monitoring/README.md)
- [API Documentation](README.md)

### External Dependencies
- [Cloudflare SSL/DNS](https://dash.cloudflare.com)
- [Sentry Error Tracking](https://sentry.io)
- [RunPod GPU Provider](https://runpod.io)

## ✅ Launch Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| DevOps Lead | _____________ | _____________ | _____ |
| Security Lead | _____________ | _____________ | _____ |
| Product Manager | _____________ | _____________ | _____ |
| Engineering Lead | _____________ | _____________ | _____ |

---

## 🔍 Troubleshooting Guide

### Common Issues

#### High Error Rate
1. Check application logs for errors
2. Verify database connectivity
3. Check external service status (RunPod, S3)
4. Review rate limiting configuration

#### Slow Response Times
1. Check database performance
2. Review connection pool settings
3. Analyze slow query logs
4. Check GPU provider latency

#### Authentication Issues
1. Verify JWT secret configuration
2. Check token expiration settings
3. Review CORS configuration
4. Validate user permissions

#### Storage Issues
1. Check S3/R2 connectivity
2. Verify bucket permissions
3. Review upload quotas
4. Check storage retention policies

### Log Analysis

#### Application Logs
```bash
# View recent errors
tail -f /var/log/oneshot/app.log | grep ERROR

# Search for specific errors
grep "DatabaseError" /var/log/oneshot/app.log | tail -20
```

#### System Metrics
```bash
# Check resource usage
top -p $(pgrep python)

# Monitor disk usage
df -h

# Check memory usage
free -h
```

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-01  
**Next Review**: 2024-02-01
# Production Security Configuration

This document outlines the security hardening applied to the production environment.

## 🔒 CORS Configuration (Strict)

### Production Settings
- **Allowed Origins**: Restricted to specific app domains only
  - `https://yourdomain.com`
  - `https://www.yourdomain.com`  
  - `https://app.yourdomain.com`
- **Credentials**: Enabled for authenticated requests
- **Methods**: Limited to essential HTTP methods only
- **Headers**: Restrictive whitelist approach

⚠️ **IMPORTANT**: Replace `yourdomain.com` with actual production domains before deployment.

### CORS Middleware Types
1. **secure-headers**: General web traffic
2. **api-cors**: API-specific (most restrictive)

## 🛡️ HTTPS & TLS Configuration

### TLS Settings
- **Minimum Version**: TLS 1.3 (strict mode) / TLS 1.2 (fallback)
- **Cipher Suites**: Modern, secure ciphers only
- **HSTS**: 1-year max-age with subdomains and preload
- **SSL Redirect**: Forced HTTPS for all traffic

### Certificate Management
- **Provider**: Cloudflare DNS Challenge
- **Auto-renewal**: Enabled via ACME
- **SNI Strict**: Enabled for security

## 🔐 Security Headers

### Applied Headers
- **X-Frame-Options**: DENY (prevents clickjacking)
- **X-Content-Type-Options**: nosniff
- **X-XSS-Protection**: 1; mode=block
- **Content-Security-Policy**: Restrictive policy
- **Referrer-Policy**: strict-origin-when-cross-origin
- **Permissions-Policy**: Restrictive permissions

### CSP Policy
```
default-src 'self'; 
script-src 'self'; 
style-src 'self' 'unsafe-inline'; 
img-src 'self' data: https:; 
font-src 'self'; 
connect-src 'self' https://api.yourdomain.com; 
frame-ancestors 'none'
```

## ⚡ Rate Limiting

### Production Limits
- **General Traffic**: 25 req/min (burst: 50)
- **API Endpoints**: 10 req/min (burst: 20)
- **Source**: IP-based with depth detection

### IP Whitelisting
- **Admin Endpoints**: Restricted to specific IP ranges
- **Health Checks**: Minimal restrictions
- **Monitoring**: Basic auth required

## 📊 Logging & Monitoring

### Log Configuration
- **Level**: WARN (production-optimized)
- **Format**: JSON structured logging
- **Retention**: 7 days (traefik.log), 30 days (access.log)
- **Compression**: Enabled for archived logs
- **Size Limits**: 100MB per file, 3-5 backups

### Access Log Privacy
- **Authorization Headers**: Dropped
- **User Agents**: Redacted
- **Personal Data**: Minimized retention

## 🚀 Router Configuration

### Priority Levels
1. **Health Checks** (300): Minimal middleware
2. **Admin Dashboard** (200): Full security stack
3. **API Traffic** (100): Production security

### Middleware Stack
1. **secure-headers**: Base security headers
2. **api-cors**: CORS policies
3. **rate-limit**: Traffic throttling
4. **compress**: Response compression
5. **auth**: Authentication (where required)

## ⚙️ Pre-Deployment Checklist

### Domain Configuration
- [ ] Replace all `yourdomain.com` references with actual domains
- [ ] Configure DNS A/AAAA records
- [ ] Verify Cloudflare API tokens

### Security Settings
- [ ] Generate strong monitoring passwords
- [ ] Configure admin IP whitelist
- [ ] Review CSP policy for app requirements
- [ ] Test CORS with actual frontend domains

### Certificates
- [ ] Verify ACME email configuration
- [ ] Test certificate generation
- [ ] Confirm automatic renewal

### Monitoring
- [ ] Configure log aggregation
- [ ] Set up security alerts
- [ ] Test rate limiting thresholds

## 🔧 Environment Variables

Required production environment variables:

```bash
# Cloudflare Configuration
ACME_EMAIL=security@yourdomain.com
CLOUDFLARE_DNS_API_TOKEN=your_token_here

# Admin Access
TRAEFIK_ADMIN_PASSWORD=hashed_password_here

# Monitoring
LOG_LEVEL=WARN
ACCESS_LOG_RETENTION_DAYS=30
```

## 📋 Security Validation

Use the following commands to validate security configuration:

```bash
# Test HTTPS redirect
curl -I http://yourdomain.com

# Verify security headers
curl -I https://yourdomain.com

# Test CORS policies
curl -H "Origin: https://malicious.com" https://api.yourdomain.com

# Check TLS configuration
nmap --script ssl-enum-ciphers -p 443 yourdomain.com
```

## 🚨 Security Monitoring

### Alert Triggers
- Rate limit violations
- Failed certificate renewals
- Unauthorized access attempts
- TLS/SSL errors

### Log Analysis
Monitor for:
- Unusual traffic patterns
- CORS violations
- Failed authentication attempts
- Certificate expiration warnings
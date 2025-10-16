# Network Timeout Fix - Permanent Solution Implementation

## Overview

This document describes the comprehensive permanent solution implemented to resolve recurring network timeout issues in the OneShot mobile application's authentication flow.

## Problem Statement

Users experienced persistent connection failures with error `ERROR Login error: [OneShotError: Network request timed out]` despite previous fixes. Root causes identified:

1. Backend server unavailability not detected before authentication attempts
2. IP address volatility due to DHCP reassignment
3. Insufficient proactive network quality monitoring
4. Generic error messages lacking actionable guidance
5. Backend binding configuration risks

## Solution Architecture

### 1. Pre-flight Connection Validator

**Location**: `frontend/oneshot-sdk/src/preflight-validator.ts`

**Purpose**: Verify backend availability before critical operations

**Key Features**:
- Quick health checks (5-second timeout)
- Connection status classification (CONNECTED, DEGRADED, DISCONNECTED, CHECKING)
- Retry support with exponential backoff
- Real-time listener notifications
- Latency-based quality assessment

**Usage**:
```typescript
const result = await oneShotClient.preflightCheck({
  timeout: 5000,
  retryOnFailure: true
});

if (!result.backendReachable) {
  console.error('Backend unavailable:', result.error);
  console.log('Recommendation:', result.recommendation);
}
```

### 2. Intelligent Service Discovery

**Location**: `frontend/oneshot-sdk/src/service-discovery.ts`

**Purpose**: Automatically detect and validate correct backend URL

**Discovery Strategy**:
1. Check explicit URL override
2. Try cached IP addresses (sorted by success count and recency)
3. Use platform-specific defaults (10.0.2.2 for Android emulator, localhost for iOS simulator)
4. Network scan for physical devices (scans common LAN IP ranges)
5. Fallback to last known good configuration

**Caching**:
- Stores successful IP addresses with timestamps
- Invalidates cache after 7 days
- Tracks success count for prioritization

**Usage**:
```typescript
oneShotClient.initServiceDiscovery(platformInfo, explicitUrl);
const result = await oneShotClient.discoverService();

console.log('Discovered URL:', result.url);
console.log('Source:', result.source); // 'cached', 'platform-default', etc.
```

### 3. Adaptive Timeout Calibration

**Location**: `frontend/oneshot-sdk/src/adaptive-timeout.ts`

**Purpose**: Dynamically adjust timeouts based on observed network performance

**Algorithm**:
```
Initial Timeout = platform_default (15s emulator, 45s physical)

After Each Request:
  observed_latency = actual_request_duration
  
  IF observed_latency > current_timeout * 0.8:
    new_timeout = observed_latency * 1.5 (approaching timeout)
  
  IF observed_latency < current_timeout * 0.3:
    new_timeout = current_timeout * 0.9 (completing quickly)
  
  timeout = (current_timeout * 0.7) + (new_timeout * 0.3) // Smooth adjustment
```

**Persistence**:
- Saves calibrated values to localStorage
- Network-specific calibration (resets on SSID change)
- 24-hour cache expiration

**Usage**:
```typescript
// Automatic - SDK records request metrics
await oneShotClient.login(email, password);

// Get calibrated timeout
const timeout = oneShotClient['timeoutCalibrator'].getCurrentTimeout();
console.log('Calibrated timeout:', timeout);
```

### 4. Enhanced Login Flow with Pre-flight

**Location**: Updated `frontend/oneshot-sdk/src/client.ts`

**Changes**:
1. Pre-flight check before authentication (can be skipped with `skipPreflight: true`)
2. Connection status verification
3. Progress feedback during slow connections
4. Request metrics recording for timeout calibration

**Usage**:
```typescript
const response = await oneShotClient.login(email, password, {
  onProgress: (message) => console.log(message),
  maxAttempts: 10,
  skipPreflight: false // Enable pre-flight check (default)
});
```

### 5. Interactive Network Diagnostics Panel

**Location**: `frontend/expo-app/src/components/NetworkDiagnosticsModal.tsx`

**Features**:
- Real-time connection status display
- Network configuration details (API URL, timeout, retry attempts)
- Network metrics (quality, latency, backend reachability)
- Interactive connection testing
- Troubleshooting guidance

**Usage in Login Screen**:
```tsx
<NetworkDiagnosticsModal
  visible={showDiagnostics}
  onClose={() => setShowDiagnostics(false)}
/>
```

### 6. Login Screen Enhancements

**Location**: `frontend/expo-app/src/screens/LoginScreen.tsx`

**New Features**:
1. **Connection Status Indicator**: Visual indicator showing CONNECTED/DEGRADED/DISCONNECTED
2. **Automatic Pre-flight Check**: Runs on screen mount
3. **Enhanced Error Messages**: Specific guidance based on error type
4. **Network Diagnostics Access**: Quick access to diagnostics modal
5. **Connection Testing**: Manual connection test button

**Visual Indicators**:
- 🟢 Green dot: Connected
- 🟡 Orange half-circle: Degraded
- 🔴 Red circle outline: Disconnected
- 🔵 Blue circle: Checking

### 7. Backend Startup Validation Scripts

**Locations**: 
- `backend/scripts/validate-backend-startup.py` (Python/Linux)
- `backend/scripts/validate-backend-startup.ps1` (PowerShell/Windows)

**Purpose**: Validate backend configuration before development

**Checks**:
1. Port availability
2. Localhost accessibility
3. Network interface accessibility
4. Firewall configuration
5. Health endpoint response

**Usage**:
```bash
# Python
python backend/scripts/validate-backend-startup.py --port 8000

# PowerShell
.\backend\scripts\validate-backend-startup.ps1 -Port 8000
```

**Output Example**:
```
============================================================
OneShot Backend Startup Validator
============================================================

Checking port 8000 availability...
✓ Port 8000 is available

Validating backend accessibility...
✓ Backend accessible on localhost
✓ Accessible on Wi-Fi (192.168.1.105)

Checking firewall configuration...
✓ Firewall rule exists for port 8000

============================================================
Network Configuration
============================================================

Localhost:        http://localhost:8000
Wi-Fi             http://192.168.1.105:8000

============================================================
Mobile Access URLs
============================================================

Android Emulator: http://10.0.2.2:8000
iOS Simulator:    http://localhost:8000
Physical Devices: http://192.168.1.105:8000

============================================================
Validation Summary
============================================================

✓ All checks passed!
Backend is ready for mobile development.
============================================================
```

## Integration with Existing Features

### Connection Monitoring

The existing `ConnectionHealthMonitor` (in `connection-monitor.ts`) can be integrated with the new pre-flight validator:

```typescript
import { ConnectionHealthMonitor } from 'oneshot-sdk';

const monitor = new ConnectionHealthMonitor(baseUrl);

monitor.addStatusListener((status) => {
  if (!status.isHealthy) {
    // Trigger pre-flight check
    oneShotClient.quickPreflightCheck();
  }
});

monitor.startMonitoring();
```

### Network Quality Assessment

The existing `NetworkQualityAssessment` works seamlessly with adaptive timeout:

```typescript
const quality = await oneShotClient.getNetworkQuality();

if (quality.quality === 'poor') {
  // Timeout already calibrated by AdaptiveTimeoutCalibrator
  console.log('Using extended timeout:', quality.recommendedTimeout);
}
```

## Usage Guide

### For Developers

#### Setup Backend

1. Start backend with proper binding:
   ```bash
   uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
   ```

2. Validate backend configuration:
   ```bash
   python backend/scripts/validate-backend-startup.py
   ```

3. Note the LAN IP address from validation output

#### Configure Mobile App

1. Update `.env` file (optional - automatic discovery enabled):
   ```env
   EXPO_PUBLIC_API_URL=http://192.168.1.105:8000
   ```

2. Initialize SDK with service discovery:
   ```typescript
   import { Platform } from 'react-native';
   import Constants from 'expo-constants';
   
   const platformInfo = {
     os: Platform.OS as 'android' | 'ios',
     isEmulator: !Constants.isDevice,
     isSimulator: !Constants.isDevice && Platform.OS === 'ios',
     isPhysicalDevice: Constants.isDevice
   };
   
   oneShotClient.initServiceDiscovery(platformInfo);
   ```

#### Test Connection

1. Open mobile app
2. Check connection status indicator on login screen
3. Tap "Network Diagnostics" to view detailed information
4. Tap "Test Connection" to run comprehensive tests

### For Users

#### Troubleshooting Connection Issues

1. **Server Not Reachable**:
   - Ensure backend is running
   - Check backend is bound to 0.0.0.0 (not 127.0.0.1)
   - Verify firewall allows connections

2. **Slow Connection**:
   - Move closer to WiFi router
   - Switch from mobile data to WiFi
   - Check network quality in diagnostics

3. **Timeout Errors**:
   - Backend may be overloaded
   - Network unstable - retry with better connection
   - View diagnostics for specific recommendations

## Performance Metrics

### Latency Targets

| Operation | Target | Maximum | Percentile |
|-----------|--------|---------|------------|
| Pre-flight Health Check | <100ms | 5000ms | 95th |
| Service Discovery (cached) | <50ms | 200ms | 99th |
| Service Discovery (scan) | <3s | 10s | 90th |
| Login with Pre-flight | <5s | 15s | 90th |

### Timeout Configuration

| Network Quality | Calibrated Timeout | Retry Count |
|-----------------|-------------------|-------------|
| Excellent (<100ms) | 10-15s | 3 |
| Good (100-300ms) | 15-30s | 5 |
| Fair (300-1000ms) | 30-45s | 7 |
| Poor (>1000ms) | 60-90s | 10 |

## Monitoring & Observability

### Key Metrics to Track

1. **Pre-flight Success Rate**: Target >95%
2. **Service Discovery Success**: Target >90%
3. **Timeout Calibration Accuracy**: Compare predicted vs actual
4. **Authentication Success After Pre-flight**: Target >98%

### Logging

All network operations log detailed information:

```typescript
// Pre-flight check
console.log('Pre-flight result:', {
  status: 'connected',
  latency: 45,
  backendReachable: true,
  recommendation: 'Good connection quality'
});

// Service discovery
console.log('Service discovered:', {
  url: 'http://192.168.1.105:8000',
  source: 'cached',
  validated: true,
  latency: 32
});

// Timeout calibration
console.log('Timeout recalibrated:', {
  oldTimeout: 30000,
  newTimeout: 22500,
  avgLatency: 150,
  successRate: 0.95
});
```

## Testing

### Unit Tests

Run SDK tests:
```bash
cd frontend/oneshot-sdk
npm test
```

### Integration Tests

Test end-to-end flow:
```bash
cd frontend/expo-app
npm run test:integration
```

### Manual Testing Checklist

- [ ] Backend running, login succeeds within 5 seconds
- [ ] Backend stopped, pre-flight detects disconnection within 5 seconds
- [ ] Slow network (throttle to 3G), login completes with increased timeout
- [ ] IP address changes, service discovery finds new IP
- [ ] Firewall blocks connection, error shows specific guidance
- [ ] Network diagnostics panel shows accurate information
- [ ] Connection status indicator updates correctly

## Rollback Plan

If issues arise, disable new features progressively:

1. **Disable Pre-flight Check**:
   ```typescript
   await oneShotClient.login(email, password, { skipPreflight: true });
   ```

2. **Disable Service Discovery**:
   Use explicit URL configuration in `.env`

3. **Disable Timeout Calibration**:
   ```typescript
   oneShotClient['timeoutCalibrator'].reset();
   oneShotClient['timeoutCalibrator'].setTimeout(30000); // Fixed timeout
   ```

4. **Revert to Previous SDK Version**:
   ```bash
   cd frontend/oneshot-sdk
   git checkout <previous-commit>
   npm install
   ```

## Future Enhancements

1. **Background Health Monitoring**: Continuous monitoring when app is in foreground
2. **Network Change Detection**: Auto-refresh service discovery on network change
3. **QR Code Backend URL Sharing**: Scan QR from backend validator output
4. **Offline Mode**: Cache last successful state for offline access
5. **Telemetry**: Anonymous network metrics for improving timeout calibration

## Migration Notes

### Updating Existing Code

Old code:
```typescript
await oneShotClient.login(email, password);
```

New code (with progress feedback):
```typescript
await oneShotClient.login(email, password, {
  onProgress: (message) => setLoadingStatus(message)
});
```

### SDK Exports

New exports available:
```typescript
import {
  PreflightValidator,
  ServiceDiscovery,
  AdaptiveTimeoutCalibrator,
  ConnectionStatus
} from 'oneshot-sdk';
```

## Support

For issues or questions:
1. Check network diagnostics panel in app
2. Run backend validation script
3. Review application logs
4. Check this documentation

## Conclusion

This permanent solution provides:
- ✅ Proactive backend availability detection
- ✅ Intelligent IP address discovery and caching
- ✅ Adaptive timeout based on observed performance
- ✅ Comprehensive diagnostics for troubleshooting
- ✅ Enhanced user experience with clear error messages
- ✅ Developer tools for backend validation

The implementation follows the design document specifications and provides a resilient, self-healing network architecture for the OneShot mobile application.

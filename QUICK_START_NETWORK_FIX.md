# Quick Start Guide - Network Timeout Permanent Fix

## Overview

This guide will help you quickly set up and test the new network resilience features implemented to eliminate timeout issues.

## Prerequisites

- Backend server running (Python FastAPI)
- Mobile development environment (Expo)
- Network connection (WiFi or mobile data)

## Step 1: Validate Backend Configuration

### Windows

Open PowerShell in the backend directory:

```powershell
cd backend
.\scripts\validate-backend-startup.ps1 -Port 8000
```

### Linux/Mac

Open terminal in the backend directory:

```bash
cd backend
python scripts/validate-backend-startup.py --port 8000
```

**Expected Output**:
```
✓ Port 8000 is available
✓ Backend accessible on localhost
✓ Accessible on Wi-Fi (192.168.1.105)
✓ Firewall rule exists for port 8000

Mobile Access URLs:
Android Emulator: http://10.0.2.2:8000
iOS Simulator:    http://localhost:8000
Physical Devices: http://192.168.1.105:8000

✓ All checks passed!
Backend is ready for mobile development.
```

**Note the LAN IP address** (e.g., 192.168.1.105) for physical devices.

## Step 2: Start Backend Server

Ensure backend is bound to all interfaces:

```bash
cd backend
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Important**: Use `--host 0.0.0.0` (not `127.0.0.1`) to allow mobile device access.

## Step 3: Configure Mobile App (Optional)

The app now includes automatic service discovery, but you can optionally set explicit URL:

Edit `frontend/expo-app/.env`:

```env
# For Android Emulator
EXPO_PUBLIC_API_URL=http://10.0.2.2:8000

# For iOS Simulator
EXPO_PUBLIC_API_URL=http://localhost:8000

# For Physical Devices (update with your LAN IP from Step 1)
EXPO_PUBLIC_API_URL=http://192.168.1.105:8000
```

**If you leave it empty**, the app will automatically detect the correct URL based on platform.

## Step 4: Install SDK Dependencies

```bash
cd frontend/oneshot-sdk
npm install
```

## Step 5: Start Mobile App

```bash
cd frontend/expo-app
npm install
npx expo start
```

## Step 6: Test Connection Features

### On Login Screen

1. **Check Connection Status Indicator**:
   - Look for status indicator below app title
   - Should show: 🟢 "Connected to server"
   
2. **Test Connection**:
   - Tap "Test Connection" button
   - Should see: "Connection Test Successful" with latency

3. **View Network Diagnostics**:
   - Tap "Network Diagnostics" button
   - Review:
     - Connection Status
     - Configuration (API URL, Timeout, Retry Attempts)
     - Network Metrics
   - Tap "🔍 Run Connection Test" for comprehensive testing

4. **Perform Login**:
   - Enter credentials
   - Watch progress messages during authentication
   - Should see adaptive messaging based on network quality

## Testing Scenarios

### Scenario 1: Normal Connection

**Setup**: Backend running, good network

**Expected**:
- Connection status: 🟢 Connected
- Login completes in <5 seconds
- No error messages

### Scenario 2: Backend Stopped

**Setup**: Stop backend server

**Expected**:
- Connection status changes to: 🔴 Server not reachable (within 5 seconds)
- Login button still enabled (to show error guidance)
- Login attempt shows: "Backend is not reachable" with specific recommendation
- Error alert offers "Network Diagnostics" button

**Steps**:
1. Stop backend: `Ctrl+C` in backend terminal
2. Wait 5 seconds
3. Observe status indicator change to red
4. Attempt login
5. See detailed error with troubleshooting options

### Scenario 3: Slow Network

**Setup**: Throttle network to 3G speed

**In Chrome DevTools** (for testing):
1. Open Chrome DevTools (F12)
2. Network tab → Throttling → Slow 3G

**Expected**:
- Connection status may show: 🟡 Connection is slow
- Login shows progressive messages:
  - Attempt 1-3: "Connecting to server..."
  - Attempt 4-6: "Connection slower than usual, retrying..."
  - Attempt 7-9: "Network appears unstable, please wait..."
- Timeout automatically increases to accommodate slow network
- Login eventually succeeds

### Scenario 4: IP Address Change

**Setup**: Change network (e.g., switch WiFi networks)

**Expected**:
- Service discovery automatically detects IP change
- App attempts to reconnect with new IP
- Connection status updates accordingly
- Login works with new network configuration

### Scenario 5: Firewall Blocks Connection

**Setup**: Enable firewall to block port 8000

**Windows**:
```powershell
New-NetFirewallRule -DisplayName "Block OneShot" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Block
```

**Expected**:
- Connection test fails with "Connection refused"
- Error message suggests checking firewall settings
- Diagnostics show specific firewall-related guidance

**Cleanup**:
```powershell
Remove-NetFirewallRule -DisplayName "Block OneShot"
```

## Troubleshooting

### Issue: Connection Status Always Red

**Possible Causes**:
1. Backend not running
2. Backend bound to 127.0.0.1 instead of 0.0.0.0
3. Firewall blocking connection
4. Wrong IP address

**Solutions**:
1. Run backend validation script: `.\scripts\validate-backend-startup.ps1`
2. Ensure backend started with `--host 0.0.0.0`
3. Check firewall rules
4. Update `.env` with correct LAN IP from validation script

### Issue: Login Timeout on Physical Device

**Possible Causes**:
1. Mobile device on different network than backend
2. Router blocks inter-device communication
3. IP address hardcoded incorrectly

**Solutions**:
1. Ensure both on same WiFi network
2. Check router settings (disable AP isolation)
3. Clear app cache and let service discovery run
4. View diagnostics to see detected configuration

### Issue: Slow Login (>10 seconds)

**Possible Causes**:
1. Poor network quality
2. Backend server overloaded
3. Timeout not calibrated yet

**Solutions**:
1. Check network quality in diagnostics panel
2. Restart backend server
3. Perform 5-10 login attempts to calibrate timeout
4. View calibration data in diagnostics

### Issue: Network Diagnostics Shows "Unknown"

**Possible Causes**:
1. Pre-flight check hasn't run yet
2. App just started

**Solutions**:
1. Wait 5 seconds for initial check
2. Tap "Refresh Data" in diagnostics
3. Tap "Test Connection" to run manual check

## Verification Checklist

After setup, verify these work:

- [ ] Backend validation script passes all checks
- [ ] Backend accessible on localhost
- [ ] Backend accessible from LAN IP
- [ ] Connection status indicator shows green (connected)
- [ ] Test connection succeeds with <100ms latency
- [ ] Network diagnostics loads correctly
- [ ] Login succeeds within 5 seconds
- [ ] Progress messages appear during login
- [ ] Stopping backend changes status to red within 5 seconds
- [ ] Error messages provide specific guidance

## Advanced Usage

### Enable Service Discovery

```typescript
import { Platform } from 'react-native';
import Constants from 'expo-constants';

const platformInfo = {
  os: Platform.OS as 'android' | 'ios',
  isEmulator: !Constants.isDevice,
  isSimulator: !Constants.isDevice && Platform.OS === 'ios',
  isPhysicalDevice: Constants.isDevice
};

// Initialize service discovery
oneShotClient.initServiceDiscovery(platformInfo);

// Discover backend URL
const result = await oneShotClient.discoverService();
console.log('Discovered:', result.url, 'Source:', result.source);
```

### Monitor Connection Health

```typescript
import { ConnectionHealthMonitor } from 'oneshot-sdk';

const monitor = new ConnectionHealthMonitor(baseUrl);

monitor.addStatusListener((status) => {
  console.log('Health status:', status.isHealthy);
  console.log('Network quality:', status.currentQuality);
  console.log('Issues:', status.issues);
  console.log('Recommendations:', status.recommendations);
});

monitor.startMonitoring();
```

### Get Calibration Data

```typescript
const calibration = oneShotClient['timeoutCalibrator'].getCalibrationData();

console.log('Current timeout:', calibration.currentTimeout);
console.log('Average latency:', calibration.averageLatency);
console.log('Success rate:', (calibration.successRate * 100).toFixed(1) + '%');
```

## Performance Metrics

Track these metrics to ensure optimal performance:

1. **Pre-flight Success Rate**: Should be >95%
   ```typescript
   // Check in diagnostics panel: Connection Status section
   ```

2. **Average Login Latency**: Should be <5 seconds
   ```typescript
   const start = performance.now();
   await oneShotClient.login(email, password);
   const latency = performance.now() - start;
   console.log('Login latency:', latency);
   ```

3. **Timeout Calibration**: Should converge after 10-20 requests
   ```typescript
   const data = oneShotClient['timeoutCalibrator'].getCalibrationData();
   console.log('Requests recorded:', data.observedLatencies.length);
   console.log('Calibrated to:', data.currentTimeout, 'ms');
   ```

## Next Steps

1. **Test with Real Users**: Deploy to TestFlight/Internal Testing
2. **Monitor Metrics**: Track pre-flight success rate, login latency
3. **Gather Feedback**: Ask users to report connection issues
4. **Iterate**: Adjust timeout calibration parameters based on telemetry

## Support

For issues:
1. Check backend validation output
2. Review network diagnostics panel
3. Check application logs
4. Consult [NETWORK_TIMEOUT_PERMANENT_FIX.md](./NETWORK_TIMEOUT_PERMANENT_FIX.md)

## Summary

You now have:
- ✅ Pre-flight connection validation
- ✅ Intelligent service discovery
- ✅ Adaptive timeout calibration
- ✅ Interactive network diagnostics
- ✅ Enhanced error messages
- ✅ Backend validation tools

The system is designed to be resilient and self-healing, automatically adapting to network conditions and providing clear guidance when issues occur.

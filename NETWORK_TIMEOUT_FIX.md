# 🔧 Network Timeout Fix - Complete Guide

## 📋 Problem Summary

**Error**: `ERROR Login error: [OneShotError: Network request timed out]`

**Root Cause**: Login requests timing out due to backend server not running or unreachable.

---

## 🔍 Diagnosis Results

### Primary Issues Identified:

1. **Backend Server Not Running** ✗
   - Port 8000 is not listening
   - No service responding to API requests
   - Client attempts to connect to non-existent server

2. **Platform-Specific URL Mapping Issues**
   - Android emulator requires `10.0.2.2` (not localhost or LAN IP)
   - iOS simulator uses `localhost` or `127.0.0.1`
   - Physical devices need LAN IP (`192.168.100.10` detected)
   - Configuration was not platform-aware

3. **Timeout Configuration**
   - 30-second timeout may be insufficient for mobile networks
   - No differentiation between emulator and physical device

4. **No Pre-flight Connectivity Check**
   - App attempts login without verifying backend availability
   - User sees generic timeout errors without helpful guidance

---

## ✅ Solutions Implemented

### 1. Platform-Aware API Configuration

**File**: `frontend/expo-app/src/utils/platformConfig.ts` (NEW)

Automatically detects platform and sets appropriate API URL:
- **Android Emulator**: `http://10.0.2.2:8000`
- **iOS Simulator**: `http://localhost:8000`
- **Physical Devices**: `http://192.168.100.10:8000` (detected LAN IP)
- **Web**: `http://localhost:8000`

**Adaptive Timeout**:
- Emulator/Simulator: 15 seconds (fast, stable connection)
- Physical Devices: 45 seconds (accounts for mobile network variability)

**Adaptive Retry Attempts**:
- Emulator/Simulator: 3 attempts
- Physical Devices: 10 attempts (mobile network instability)

### 2. Enhanced SDK Client Configuration

**File**: `frontend/expo-app/src/utils/client.ts` (UPDATED)

- Uses platform-aware configuration
- Logs detailed configuration on startup
- Exports platform info for diagnostics

### 3. API Connectivity Check Script

**File**: `frontend/expo-app/scripts/check-api.js` (NEW)

Tests backend connectivity before starting the app:
- Health endpoint check
- Auth endpoint verification
- Latency measurement
- Detailed error diagnosis

**Usage**:
```bash
npm run check:api
```

### 4. Backend Startup Helper

**File**: `backend/start-server.ps1` (NEW)

Automated backend startup with:
- Environment validation
- Dependency checks
- Virtual environment activation
- Port conflict detection
- Network configuration display

**Usage**:
```powershell
cd backend
.\start-server.ps1
```

### 5. Enhanced app.config.js

**File**: `frontend/expo-app/app.config.js` (UPDATED)

- Improved LAN IP detection
- Better logging for debugging
- Platform-specific notes

### 6. Package.json Scripts

**File**: `frontend/expo-app/package.json` (UPDATED)

New scripts added:
- `npm run check:api` - Test API connectivity
- `npm run reset:metro` - Reset Metro bundler cache
- `npm run doctor` - Run Expo diagnostics
- `prestart` hook - Auto-check API before starting app

---

## 🚀 Quick Start Guide

### Step 1: Start the Backend

Open PowerShell in the backend directory:

```powershell
cd "c:\Users\54587\Desktop\qoder deneme\backend"
.\start-server.ps1
```

Expected output:
```
==================================================
OneShot Backend Startup
==================================================

Server Configuration
Host: 0.0.0.0 (all interfaces)
Port: 8000
Local IP: 192.168.100.10

Access URLs:
  - Localhost: http://localhost:8000
  - LAN IP: http://192.168.100.10:8000
  - Android Emulator: http://10.0.2.2:8000
  - iOS Simulator: http://localhost:8000

Health Check: http://localhost:8000/healthz
API Docs: http://localhost:8000/docs
==================================================

Starting server...
```

### Step 2: Verify Backend is Running

Open a new PowerShell window:

```powershell
curl http://localhost:8000/healthz
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": 1697558400000,
  "service": "oneshot-api",
  "version": "2.0.0"
}
```

### Step 3: Test API Connectivity

In the Expo app directory:

```powershell
cd "c:\Users\54587\Desktop\qoder deneme\frontend\expo-app"
npm run check:api
```

Expected output:
```
🔍 Checking API connectivity...
📡 API URL: http://192.168.100.10:8000
⏱️  Timeout: 5000ms

✅ Health check PASSED
📊 Status: 200
⚡ Latency: 45ms

🔐 Testing auth endpoint...
✅ Auth endpoint is REACHABLE
📊 Status: 401 (expected 401 for invalid credentials)
⚡ Latency: 82ms

==================================================
✅ API is FULLY OPERATIONAL

Next steps:
  1. Start the Expo app: npm start
  2. Run on Android: press "a"
  3. Run on iOS: press "i"
```

### Step 4: Start the Mobile App

```powershell
npm start
```

The app will now:
1. Auto-detect your platform (Android/iOS emulator or physical device)
2. Configure the correct API URL
3. Use appropriate timeout and retry settings
4. Display detailed configuration in console

---

## 🔧 Troubleshooting

### Issue: Backend won't start

**Symptom**: Port 8000 already in use

**Solution**:
```powershell
# Find process using port 8000
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object {
    Get-Process -Id $_.OwningProcess
}

# Kill the process (replace PID with actual process ID)
Stop-Process -Id <PID> -Force
```

### Issue: Connection timeout on Android Emulator

**Symptom**: `Unable to reach server`

**Checklist**:
1. ✓ Backend running on `0.0.0.0:8000`
2. ✓ App configured with `http://10.0.2.2:8000`
3. ✓ No firewall blocking port 8000
4. ✓ Emulator has internet access

**Test**:
```bash
# Inside Android emulator (adb shell)
adb shell
curl http://10.0.2.2:8000/healthz
```

### Issue: Connection timeout on iOS Simulator

**Symptom**: `Request timed out`

**Checklist**:
1. ✓ Backend running on `localhost:8000`
2. ✓ App configured with `http://localhost:8000`
3. ✓ Xcode simulator network settings enabled

**Test**:
```bash
# On Mac terminal
curl http://localhost:8000/healthz
```

### Issue: Connection timeout on Physical Device

**Symptom**: `Network request failed`

**Checklist**:
1. ✓ Device on same WiFi network as development machine
2. ✓ Backend running on `0.0.0.0:8000` (not `127.0.0.1`)
3. ✓ Firewall allows port 8000 (Windows Defender / antivirus)
4. ✓ App configured with correct LAN IP (`192.168.100.10`)

**Windows Firewall Configuration**:
```powershell
# Add firewall rule
New-NetFirewallRule -DisplayName "OneShot Backend" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

**Test**:
```bash
# From physical device (using browser)
http://192.168.100.10:8000/healthz
```

### Issue: Firewall blocking connections

**Windows Defender Firewall**:
1. Open Windows Defender Firewall
2. Click "Allow an app or feature through Windows Defender Firewall"
3. Click "Change settings" → "Allow another app"
4. Find Python (or uvicorn) and allow both Private and Public networks

**Third-party Antivirus/Firewall**:
- Add exception for port 8000
- Allow Python/uvicorn process
- Temporarily disable to test (not recommended for production)

### Issue: VPN interfering with connection

**Symptom**: Works without VPN, fails with VPN

**Solutions**:
1. Disconnect VPN during development
2. Configure VPN to allow local network access (split tunneling)
3. Use explicit LAN IP in `.env` file

---

## 📊 Network Diagnostics

### In-App Network Info

The app now includes a Network Diagnostics screen:

1. Open Login screen
2. Tap "Test Connection" button
3. View detailed network information
4. Run connectivity tests

### Console Logging

When the app starts, you'll see:

```
==================================================
Platform Configuration
==================================================
Platform: android
Device Type: Emulator/Simulator
API URL: http://10.0.2.2:8000
Timeout: 15000ms
Retry Attempts: 3
Device Name: sdk_gphone64_arm64
Is Device: false
==================================================

[OneShot] SDK Configuration:
  API URL: http://10.0.2.2:8000
  Timeout: 15000ms
  Retry Attempts: 3
  Platform: android
  Device Type: Emulator/Simulator
```

---

## 🧪 Testing Different Scenarios

### Test 1: Backend Down

1. Stop the backend server
2. Try to login
3. Expected: Clear error message with "Test Connection" option

### Test 2: Slow Network

1. Enable network throttling in browser DevTools
2. Try to login
3. Expected: Progressive retry with status updates

### Test 3: Invalid Credentials

1. Backend running
2. Login with wrong password
3. Expected: Immediate "Invalid email or password" message (no retry)

### Test 4: Platform Detection

1. Run on different platforms (Android emulator, iOS simulator, physical device)
2. Check console logs
3. Verify correct API URL for each platform

---

## 📝 Configuration Files

### Backend Configuration

**File**: `backend/.env`

```env
# Server will listen on all interfaces (required for mobile access)
# Don't change this unless you know what you're doing

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8081,http://192.168.100.10:8081,http://10.0.2.2:8081

# Other settings...
```

### Frontend Configuration

**File**: `frontend/expo-app/.env`

```env
# Optional: override detected LAN API endpoint
# Leave empty for auto-detection
EXPO_PUBLIC_API_URL=

# API port (default: 8000)
EXPO_PUBLIC_API_PORT=8000

# API timeout (default: auto-adjusted based on platform)
# Emulator/Simulator: 15000ms
# Physical Device: 45000ms
EXPO_PUBLIC_API_TIMEOUT=
```

**Platform Override Examples**:

For Android Emulator only:
```env
EXPO_PUBLIC_API_URL=http://10.0.2.2:8000
```

For iOS Simulator only:
```env
EXPO_PUBLIC_API_URL=http://localhost:8000
```

For Physical Devices only:
```env
EXPO_PUBLIC_API_URL=http://192.168.100.10:8000
```

---

## 🎯 Final Verification Checklist

Before running the app, ensure:

- [ ] Backend server running on port 8000
- [ ] Health endpoint responding: `curl http://localhost:8000/healthz`
- [ ] API connectivity check passes: `npm run check:api`
- [ ] Firewall allows port 8000
- [ ] Device/emulator on same network (for physical devices)
- [ ] Platform-specific URL configured correctly
- [ ] Console shows correct platform configuration

---

## 📚 Additional Resources

### Backend Server Commands

```powershell
# Start server with script
.\start-server.ps1

# Start server manually
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

# Check if server is running
Get-NetTCPConnection -LocalPort 8000 -State Listen

# View server logs
# (Server logs appear in the terminal where you started the server)
```

### Frontend App Commands

```bash
# Check API connectivity
npm run check:api

# Reset Metro bundler cache
npm run reset:metro

# Run Expo diagnostics
npm run doctor

# Start app (auto-checks API first)
npm start

# Start app without API check
npm start --no-verify
```

### Network Testing

```powershell
# Test from development machine
curl http://localhost:8000/healthz

# Test LAN access
curl http://192.168.100.10:8000/healthz

# Test from Android emulator (via adb)
adb shell curl http://10.0.2.2:8000/healthz
```

---

## ✨ Success Criteria

After implementing these fixes:

✅ **Login completes within timeout period**
- Emulator: < 15 seconds
- Physical device: < 45 seconds (with retries)

✅ **Clear error messages**
- No generic "timeout" errors
- Actionable troubleshooting steps
- "Test Connection" and "Demo Mode" options

✅ **Platform-specific configuration works**
- Android emulator: `10.0.2.2`
- iOS simulator: `localhost`
- Physical devices: LAN IP

✅ **Resilient network handling**
- Progressive backoff retry
- Up to 10 attempts on mobile
- Adaptive timeout based on network quality

✅ **Developer experience**
- Clear console logging
- Automated connectivity checks
- Easy backend startup

---

## 🔄 Maintenance

### Updating API URL

If your LAN IP changes:

1. Check new IP: `ipconfig` (Windows) or `ifconfig` (Mac/Linux)
2. Update `backend/start-server.ps1` (automatic detection)
3. Clear app data and restart
4. Or manually set in `frontend/expo-app/.env`:
   ```env
   EXPO_PUBLIC_API_URL=http://NEW_IP:8000
   ```

### Monitoring

The backend includes:
- Health check endpoint: `/healthz`
- Readiness check: `/readyz`
- Metrics endpoint: `/metrics` (Prometheus format)
- API docs: `/docs` (development only)

---

## 🆘 Support

If issues persist:

1. Run full diagnostics:
   ```bash
   npm run doctor
   npm run check:api
   ```

2. Check backend logs for errors

3. Verify network configuration:
   - Firewall settings
   - VPN status
   - WiFi network (same for all devices)

4. Test with `curl` from different locations:
   - Development machine
   - Emulator (via adb shell)
   - Physical device browser

5. Review platform-specific documentation:
   - [Expo Network Configuration](https://docs.expo.dev/guides/networking/)
   - [Android Emulator Networking](https://developer.android.com/studio/run/emulator-networking)
   - [iOS Simulator Networking](https://developer.apple.com/documentation/xcode/running-your-app-in-simulator-or-on-a-device)

---

**Last Updated**: 2025-10-16  
**Version**: 1.0.0

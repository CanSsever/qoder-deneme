# Mobile Connectivity Fix Summary

This document summarizes all the changes made to fix the "Network request failed" error in the Expo mobile client when trying to register or login.

## Issues Identified

1. **Backend Host Configuration**: The FastAPI backend was running on `127.0.0.1` (localhost), making it inaccessible from other devices on the network.
2. **Environment Variable Configuration**: The Expo app was not properly configured to use the API_URL from the .env file.
3. **Missing Documentation**: No clear instructions for setting up the development environment for mobile connectivity.

## Changes Made

### 1. Backend Configuration (main.py)

**Before:**
```python
uvicorn.run(
    "apps.api.main:app",
    host="127.0.0.1",  # Only accessible locally
    port=8000,
    reload=True,
    log_level="info"
)
```

**After:**
```python
uvicorn.run(
    "apps.api.main:app",
    host="0.0.0.0",  # Accessible from network
    port=8000,
    reload=True,
    log_level="info"
)
```

### 2. Expo App Configuration (app.json)

**Added extra configuration:**
```json
"extra": {
  "apiUrl": "http://192.168.100.10:8000",
  "apiTimeout": 30000
}
```

This ensures the Expo app can access the API_URL through `Constants.expoConfig?.extra?.apiUrl`.

### 3. Environment Configuration (.env.example)

**Updated with clearer instructions:**
```env
# For local development, use your machine's LAN IP address
# Find your IP with: ipconfig (Windows) or ifconfig (Mac/Linux)
API_URL=http://192.168.1.100:8000
```

### 4. Documentation

Created comprehensive documentation:
- `DEVELOPMENT_SETUP.md` - Complete guide for setting up mobile development
- `test_connection.js` - Script to verify connectivity configuration

## Verification Steps

1. ✅ Backend now runs on `0.0.0.0:8000` (accessible from network)
2. ✅ Expo app properly reads API_URL from app.json extra config
3. ✅ Environment variables documented with clear examples
4. ✅ Comprehensive setup guide created

## How to Test the Fix

1. **Start the backend:**
   ```bash
   make dev
   ```

2. **Verify backend is accessible:**
   - From your development machine: `curl http://localhost:8000/healthz`
   - From another device on the same network: `curl http://YOUR_LAN_IP:8000/healthz`

3. **Update Expo app configuration:**
   - Ensure `.env` has the correct LAN IP
   - Verify `app.json` has the extra configuration

4. **Start the Expo app:**
   ```bash
   cd frontend/expo-app
   npm start
   ```

5. **Test registration/login from mobile device**

## Additional Considerations

### Windows Firewall
Ensure Windows Firewall allows connections on port 8000:
1. Open Windows Defender Firewall
2. Create inbound rule for TCP port 8000
3. Apply to all profiles (Domain, Private, Public)

### Alternative: ngrok
If local network connectivity is problematic:
1. Install ngrok: https://ngrok.com/download
2. Start backend: `make dev`
3. Run: `ngrok http 8000`
4. Update `.env` with ngrok URL

## Expected Results

After implementing these changes:
- ✅ Mobile app can successfully connect to backend
- ✅ Registration and login requests work without "Network request failed" errors
- ✅ API endpoints are accessible from mobile devices
- ✅ Clear documentation for future setup

## Troubleshooting

If you still encounter issues:

1. **Verify backend is running:**
   ```bash
   make dev
   ```

2. **Check your LAN IP:**
   - Windows: `ipconfig`
   - Mac/Linux: `ifconfig`

3. **Test connectivity manually:**
   - Open mobile browser
   - Navigate to `http://YOUR_LAN_IP:8000/healthz`

4. **Check Windows Firewall settings**
5. **Refer to DEVELOPMENT_SETUP.md for detailed instructions**
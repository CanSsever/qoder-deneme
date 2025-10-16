# 🚀 OneShot - Quick Start Guide

## 📦 Prerequisites

- **Backend**: Python 3.8+, Virtual Environment
- **Frontend**: Node.js 16+, npm, Expo CLI
- **Mobile**: Android Studio (for Android) or Xcode (for iOS)

---

## ⚡ Quick Start (3 Steps)

### 1️⃣ Start Backend Server

```powershell
# Navigate to backend directory
cd "c:\Users\54587\Desktop\qoder deneme\backend"

# Run startup script (handles everything automatically)
.\start-server.ps1
```

**Expected Output**:
```
✓ Backend running on http://192.168.100.10:8000
✓ Health check: http://localhost:8000/healthz
✓ API Docs: http://localhost:8000/docs
```

### 2️⃣ Test API Connectivity

```powershell
# Navigate to frontend app directory
cd "c:\Users\54587\Desktop\qoder deneme\frontend\expo-app"

# Test API connection
npm run check:api
```

**Expected Output**:
```
✅ Health check PASSED
✅ Auth endpoint is REACHABLE
✅ API is FULLY OPERATIONAL
```

### 3️⃣ Start Mobile App

```powershell
# Start Expo development server
npm start
```

**Then**:
- Press `a` for Android emulator
- Press `i` for iOS simulator
- Scan QR code with Expo Go app for physical device

---

## 🔧 Troubleshooting

### ❌ Backend Not Running

**Error**: `Connection refused` or `Cannot reach server`

**Fix**:
```powershell
cd backend
.\start-server.ps1
```

### ❌ Port 8000 Already in Use

**Fix**:
```powershell
# Find process
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Get-Process -Id $_.OwningProcess }

# Kill process (replace <PID> with actual ID)
Stop-Process -Id <PID> -Force
```

### ❌ Firewall Blocking

**Fix**: Add Windows Firewall rule
```powershell
New-NetFirewallRule -DisplayName "OneShot Backend" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

### ❌ Wrong IP Address

**Check your IP**:
```powershell
ipconfig | Select-String "IPv4"
```

**Update in `.env`** if needed:
```env
EXPO_PUBLIC_API_URL=http://YOUR_IP:8000
```

---

## 📱 Platform-Specific URLs

| Platform | API URL |
|----------|---------|
| **Android Emulator** | `http://10.0.2.2:8000` |
| **iOS Simulator** | `http://localhost:8000` |
| **Physical Device** | `http://192.168.100.10:8000` |
| **Web Browser** | `http://localhost:8000` |

> **Note**: The app auto-detects platform and uses the correct URL

---

## 📊 Useful Commands

### Backend
```powershell
# Start server
.\start-server.ps1

# Start manually
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

# Check if running
Get-NetTCPConnection -LocalPort 8000 -State Listen

# Test health
curl http://localhost:8000/healthz
```

### Frontend
```bash
# Test API connectivity
npm run check:api

# Start app
npm start

# Reset cache
npm run reset:metro

# Run diagnostics
npm run doctor
```

---

## ✅ Success Checklist

Before starting development:

- [ ] Backend server running on port 8000
- [ ] `npm run check:api` passes
- [ ] Firewall allows port 8000
- [ ] Device/emulator on same WiFi (for physical devices)
- [ ] Console shows correct platform configuration

---

## 📚 Full Documentation

For detailed troubleshooting and configuration:
- **Network Fix Guide**: `NETWORK_TIMEOUT_FIX.md`
- **Backend README**: `backend/README.md`
- **Frontend Guide**: `frontend/expo-app/DEVELOPMENT_SETUP.md`

---

## 🆘 Common Issues

### Login Timeout
1. Check backend is running: `curl http://localhost:8000/healthz`
2. Test API: `npm run check:api`
3. Check platform URL matches (see table above)

### Connection Refused
1. Start backend: `.\start-server.ps1`
2. Check firewall settings
3. Verify port 8000 is not in use

### Wrong Network
1. Ensure backend runs on `0.0.0.0` (all interfaces)
2. Check device and computer on same WiFi
3. Verify LAN IP is correct

---

**Need Help?** Check `NETWORK_TIMEOUT_FIX.md` for comprehensive troubleshooting guide.

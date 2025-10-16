# Development Setup Guide

This guide explains how to set up the OneShot Expo mobile client for local development.

## Prerequisites

1. Ensure the OneShot backend API is running
2. Know your development machine's LAN IP address
3. Configure Windows Firewall to allow connections on port 8000

## Step 1: Start the Backend API

From the project root directory, run:

```bash
cd backend && make dev
```

This will start the FastAPI backend on `0.0.0.0:8000`, making it accessible from other devices on your network.

## Step 2: Find Your LAN IP Address

### Windows:
1. Open Command Prompt
2. Run `ipconfig`
3. Look for your active network adapter's IPv4 address (typically something like 192.168.x.x)

### Mac/Linux:
1. Open Terminal
2. Run `ifconfig` or `ip addr`
3. Look for your active network adapter's IP address

## Step 3: Configure the Expo App

1. Copy `.env.example` to `.env` (if you have not already):
   ```bash
   cp .env.example .env
   ```

2. By default the Expo config now autodetects your current LAN IP each time it starts.
   Only set `EXPO_PUBLIC_API_URL` when you need to override the detected value:
   ```env
   EXPO_PUBLIC_API_URL=http://YOUR_LAN_IP:8000
   EXPO_PUBLIC_API_PORT=8000
   ```
   Leave `EXPO_PUBLIC_API_URL` blank to keep auto-detection.

## Step 4: Configure Windows Firewall

To allow the mobile app to connect to your backend:

1. Open Windows Defender Firewall
2. Click "Advanced settings"
3. Click "Inbound Rules" -> "New Rule"
4. Select "Port" -> "TCP" -> Specific local ports: `8000`
5. Allow the connection
6. Apply to all profiles (Domain, Private, Public)
7. Name the rule "OneShot API"

## Step 5: Test the Connection

1. Start the Expo development server:
   ```bash
   npm start
   ```

2. Test if the API is accessible from your mobile device:
   - Open a mobile browser
   - Navigate to `http://YOUR_LAN_IP:8000/healthz`
   - You should see a health check response

## Alternative: Using ngrok for Testing

If you're having trouble with local network connections, you can use ngrok:

1. Install ngrok: https://ngrok.com/download
2. Start the backend API: `cd backend && make dev`
3. In another terminal, run: `ngrok http 8000`
4. Update your `.env` file with the ngrok URL:
   ```env
   EXPO_PUBLIC_API_URL=https://YOUR_NGROK_URL.ngrok.io
   ```

## Troubleshooting

### "Network request failed" Error

1. Verify the backend is running with `cd backend && make dev`
2. Check that your LAN IP is correct
3. Ensure Windows Firewall allows connections on port 8000
4. Confirm that the Expo logs show the correct autodetected API URL
5. Test connectivity by accessing `http://YOUR_LAN_IP:8000/healthz` from your mobile browser
6. Try using ngrok as an alternative

### Registration/Login Issues

1. Ensure the backend database is set up: `make migrate`
2. Check that the API is responding correctly by testing endpoints manually
3. Verify `EXPO_PUBLIC_API_URL` (if set) points to a reachable backend

## Development Workflow

1. Start backend: `cd backend && make dev`
2. In another terminal, navigate to `frontend/expo-app`
3. Start Expo: `npm start`
4. Scan the QR code with the Expo Go app or use an emulator

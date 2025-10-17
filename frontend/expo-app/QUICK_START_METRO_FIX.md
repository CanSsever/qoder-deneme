# Quick Start: Metro SDK Resolution Fix

## TL;DR

The Expo app now automatically handles local SDK resolution in all development modes (tunnel, LAN, localhost).

## First Time Setup

```bash
cd frontend/expo-app
npm run setup:dev
```

This single command:
- ✓ Installs SDK dependencies
- ✓ Builds the SDK
- ✓ Installs Expo app dependencies
- ✓ Verifies everything is configured correctly

## Daily Development

### Start Expo in Tunnel Mode

```bash
npm run dev:tunnel
```

### Start Expo in LAN Mode

```bash
npm run dev:lan
```

### Start Expo in Local Mode

```bash
npm run dev
```

### Standard Start (with automatic verification)

```bash
npm start
```

## What Changed?

### New Files

1. **`metro.config.js`** - Metro bundler configuration for SDK resolution
2. **`scripts/verify-sdk.js`** - Automatic SDK build verification
3. **`scripts/setup-dev.js`** - One-time development setup

### Updated Files

1. **`package.json`** - Added new scripts for SDK management

## New Scripts

| Command | What It Does |
|---------|-------------|
| `npm run setup:dev` | Initial setup (run once) |
| `npm run dev:tunnel` | Start in tunnel mode |
| `npm run dev:lan` | Start in LAN mode |
| `npm run verify:sdk` | Check SDK build status |
| `npm run build:sdk` | Manually build SDK |

## How It Works

1. **Before Start**: SDK is automatically verified and built if needed
2. **Metro Config**: Maps `oneshot-sdk` to `../oneshot-sdk` directory
3. **Watch Folders**: Metro watches both app and SDK for changes
4. **Build Check**: Ensures dist/ directory has all compiled files

## Troubleshooting

### Issue: Module resolution error

```bash
npm run reset:metro
```

### Issue: SDK not found

```bash
npm run build:sdk
```

### Issue: Any other problems

```bash
npm run setup:dev
```

## When You Update the SDK

After making changes to SDK source files:

```bash
cd ../oneshot-sdk
npm run build
```

Metro will automatically reload the app.

## More Details

See [METRO_SDK_RESOLUTION_FIX.md](./METRO_SDK_RESOLUTION_FIX.md) for:
- Detailed architecture explanation
- Configuration details
- Troubleshooting guide
- Best practices
- Testing procedures

## Environment Variables

```bash
# Disable automatic SDK building
export SDK_AUTO_BUILD=false

# Enable strict timestamp checking
export SDK_STRICT_MODE=true
```

## Requirements

- Node.js 16+
- npm or yarn
- Expo CLI

## Support

1. Check SDK build: `npm run verify:sdk`
2. Clear Metro cache: `npm run reset:metro`
3. Re-run setup: `npm run setup:dev`

---

**That's it!** You can now run Expo in tunnel mode without module resolution errors. 🚀

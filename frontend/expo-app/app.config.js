const os = require('os');

/**
 * Resolve a LAN-reachable IPv4 address for the current machine.
 * Prefers private network ranges so physical devices on the same Wi-Fi
 * can reach the backend directly.
 */
function resolveLocalIp() {
  const interfaces = os.networkInterfaces();
  const candidates = [];

  for (const iface of Object.values(interfaces)) {
    if (!iface) continue;
    for (const address of iface) {
      if (address.family !== 'IPv4' || address.internal) {
        continue;
      }

      const ip = address.address;
      if (!ip || ip.startsWith('169.254.')) {
        continue;
      }

      candidates.push(ip);
    }
  }

  const preferred = candidates.find(ip =>
    ip.startsWith('192.168.') ||
    ip.startsWith('10.') ||
    ip.startsWith('172.')
  );

  return preferred || candidates[0] || null;
}

/**
 * Compute the API base URL.
 * - Respect EXPO_PUBLIC_API_URL when provided.
 * - Otherwise use the detected LAN IP with the configured port.
 * - Special handling for Android emulator (10.0.2.2) and iOS simulator (localhost)
 * - Fall back to localhost to keep web builds working.
 * 
 * Platform-specific defaults:
 * - Android Emulator: http://10.0.2.2:PORT (localhost on host machine)
 * - iOS Simulator: http://localhost:PORT or http://127.0.0.1:PORT
 * - Physical devices: http://LAN_IP:PORT (detected local network IP)
 * - Web: http://localhost:PORT
 */
function resolveApiUrl() {
  const explicitUrl = process.env.EXPO_PUBLIC_API_URL;
  if (explicitUrl && explicitUrl.trim().length > 0) {
    console.log('[app.config] Using explicit API URL:', explicitUrl);
    return explicitUrl.trim();
  }

  const port = process.env.EXPO_PUBLIC_API_PORT || '8000';
  const localIp = resolveLocalIp();

  if (localIp) {
    const apiUrl = `http://${localIp}:${port}`;
    console.log('[app.config] Detected LAN IP:', localIp);
    console.log('[app.config] Using API URL:', apiUrl);
    console.log('[app.config] Note: Android emulator should override with 10.0.2.2');
    return apiUrl;
  }

  const fallbackUrl = `http://127.0.0.1:${port}`;
  console.log('[app.config] No LAN IP detected, using fallback:', fallbackUrl);
  return fallbackUrl;
}

function resolveApiTimeout() {
  const timeout = Number(process.env.EXPO_PUBLIC_API_TIMEOUT);
  return Number.isFinite(timeout) && timeout > 0 ? timeout : 30000;
}

/** @type {import('@expo/config-types').ExpoConfig} */
const baseConfig = {
  name: 'OneShot Sample',
  slug: 'oneshot-sample',
  version: '1.0.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'light',
  splash: {
    image: './assets/splash.png',
    resizeMode: 'contain',
    backgroundColor: '#ffffff'
  },
  assetBundlePatterns: ['**/*'],
  ios: {
    supportsTablet: true
  },
  android: {
    adaptiveIcon: {
      foregroundImage: './assets/adaptive-icon.png',
      backgroundColor: '#FFFFFF'
    }
  },
  web: {
    favicon: './assets/favicon.png'
  }
};

module.exports = ({ config } = { config: {} }) => {
  const resolvedConfig = config ?? {};
  const apiUrl = resolveApiUrl();
  const apiTimeout = resolveApiTimeout();

  return {
    ...baseConfig,
    ...resolvedConfig,
    extra: {
      ...(resolvedConfig.extra ?? {}),
      apiUrl,
      apiTimeout
    }
  };
};

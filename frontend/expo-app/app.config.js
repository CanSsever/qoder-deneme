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
 * - Fall back to localhost to keep web builds working.
 */
function resolveApiUrl() {
  const explicitUrl = process.env.EXPO_PUBLIC_API_URL;
  if (explicitUrl && explicitUrl.trim().length > 0) {
    return explicitUrl.trim();
  }

  const port = process.env.EXPO_PUBLIC_API_PORT || '8000';
  const localIp = resolveLocalIp();

  if (localIp) {
    return `http://${localIp}:${port}`;
  }

  return `http://127.0.0.1:${port}`;
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

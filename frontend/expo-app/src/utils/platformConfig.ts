/**
 * Platform-aware API configuration utility
 * 
 * Handles platform-specific API URL resolution:
 * - Android Emulator: 10.0.2.2 maps to host's localhost
 * - iOS Simulator: localhost or 127.0.0.1
 * - Physical devices: LAN IP address (must be on same network)
 * - Web: localhost or deployed URL
 */
import { Platform } from 'react-native';
import Constants from 'expo-constants';

export interface PlatformConfig {
  apiUrl: string;
  timeout: number;
  retryAttempts: number;
  platform: string;
  isEmulator: boolean;
  isPhysicalDevice: boolean;
}

/**
 * Detect if running on an emulator/simulator
 */
function isRunningOnEmulator(): boolean {
  // Check if running on simulator/emulator
  if (Platform.OS === 'android') {
    // Android emulator detection
    return (
      Constants.isDevice === false ||
      Constants.deviceName?.toLowerCase().includes('emulator') ||
      Constants.deviceName?.toLowerCase().includes('sdk')
    );
  } else if (Platform.OS === 'ios') {
    // iOS simulator detection
    return Constants.isDevice === false;
  }
  
  return false;
}

/**
 * Get the appropriate API base URL for the current platform
 */
export function getPlatformApiUrl(): string {
  // First check for explicit override in env
  const explicitUrl = Constants.expoConfig?.extra?.apiUrl;
  
  if (explicitUrl && explicitUrl.trim().length > 0) {
    console.log('[PlatformConfig] Using explicit API URL:', explicitUrl);
    return explicitUrl.trim();
  }
  
  // Get port from config
  const port = process.env.EXPO_PUBLIC_API_PORT || '8000';
  
  // Platform-specific URL resolution
  if (Platform.OS === 'android') {
    const isEmulator = isRunningOnEmulator();
    
    if (isEmulator) {
      // Android emulator: use 10.0.2.2 to reach host's localhost
      const emulatorUrl = `http://10.0.2.2:${port}`;
      console.log('[PlatformConfig] Android emulator detected, using:', emulatorUrl);
      return emulatorUrl;
    } else {
      // Physical Android device: use LAN IP from config
      const lanUrl = explicitUrl || `http://192.168.100.10:${port}`;
      console.log('[PlatformConfig] Physical Android device, using LAN IP:', lanUrl);
      return lanUrl;
    }
  } else if (Platform.OS === 'ios') {
    const isSimulator = isRunningOnEmulator();
    
    if (isSimulator) {
      // iOS simulator: use localhost
      const simulatorUrl = `http://localhost:${port}`;
      console.log('[PlatformConfig] iOS simulator detected, using:', simulatorUrl);
      return simulatorUrl;
    } else {
      // Physical iOS device: use LAN IP from config
      const lanUrl = explicitUrl || `http://192.168.100.10:${port}`;
      console.log('[PlatformConfig] Physical iOS device, using LAN IP:', lanUrl);
      return lanUrl;
    }
  } else if (Platform.OS === 'web') {
    // Web: use localhost or deployed URL
    const webUrl = explicitUrl || `http://localhost:${port}`;
    console.log('[PlatformConfig] Web platform, using:', webUrl);
    return webUrl;
  }
  
  // Fallback
  const fallbackUrl = `http://localhost:${port}`;
  console.log('[PlatformConfig] Unknown platform, using fallback:', fallbackUrl);
  return fallbackUrl;
}

/**
 * Get platform-aware timeout configuration
 * - Emulators/Simulators: shorter timeout (15s)
 * - Physical devices: longer timeout (45s) to account for mobile network
 */
export function getPlatformTimeout(): number {
  const configTimeout = Constants.expoConfig?.extra?.apiTimeout;
  
  if (configTimeout && configTimeout > 0) {
    return configTimeout;
  }
  
  const isEmulator = isRunningOnEmulator();
  
  if (isEmulator) {
    // Emulators typically have fast, stable connections
    return 15000; // 15 seconds
  } else {
    // Physical devices may have slower mobile networks
    return 45000; // 45 seconds
  }
}

/**
 * Get platform-aware retry configuration
 */
export function getPlatformRetryAttempts(): number {
  const isEmulator = isRunningOnEmulator();
  
  if (isEmulator) {
    // Emulators: fewer retries (connection is usually stable)
    return 3;
  } else {
    // Physical devices: more retries (mobile networks can be unstable)
    return 10;
  }
}

/**
 * Get comprehensive platform configuration
 */
export function getPlatformConfig(): PlatformConfig {
  const isEmulator = isRunningOnEmulator();
  
  return {
    apiUrl: getPlatformApiUrl(),
    timeout: getPlatformTimeout(),
    retryAttempts: getPlatformRetryAttempts(),
    platform: Platform.OS,
    isEmulator,
    isPhysicalDevice: !isEmulator
  };
}

/**
 * Log platform configuration for debugging
 */
export function logPlatformConfig(): void {
  const config = getPlatformConfig();
  
  console.log('='.repeat(50));
  console.log('Platform Configuration');
  console.log('='.repeat(50));
  console.log('Platform:', config.platform);
  console.log('Device Type:', config.isEmulator ? 'Emulator/Simulator' : 'Physical Device');
  console.log('API URL:', config.apiUrl);
  console.log('Timeout:', config.timeout + 'ms');
  console.log('Retry Attempts:', config.retryAttempts);
  console.log('Device Name:', Constants.deviceName);
  console.log('Is Device:', Constants.isDevice);
  console.log('='.repeat(50));
}

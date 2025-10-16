/**
 * Platform-aware API configuration resolver
 * 
 * Automatically resolves the correct API base URL based on the platform:
 * - Android Emulator: 10.0.2.2 maps to host's localhost
 * - iOS Simulator: localhost
 * - Physical devices: LAN IP address
 * - Web: localhost or deployed URL
 */
import { Platform } from 'react-native';
import Constants from 'expo-constants';

/**
 * Resolve the appropriate API base URL for the current platform
 */
export function resolveBaseURL(): string {
  // Check for explicit override first
  const explicitUrl = process.env.EXPO_PUBLIC_API_URL;
  if (explicitUrl && explicitUrl.trim().length > 0) {
    console.log('[API Config] Using explicit URL:', explicitUrl);
    return explicitUrl.trim();
  }

  // Get port from config
  const port = process.env.EXPO_PUBLIC_API_PORT || '8000';

  // Platform-specific URL resolution
  if (Platform.OS === 'android') {
    // Check if running on emulator
    const isEmulator = !Constants.isDevice;
    
    if (isEmulator) {
      // Android emulator: 10.0.2.2 maps to host's localhost
      const url = process.env.EXPO_PUBLIC_API_URL_ANDROID || `http://10.0.2.2:${port}`;
      console.log('[API Config] Android Emulator detected:', url);
      return url;
    } else {
      // Physical Android device: use LAN IP
      const url = process.env.EXPO_PUBLIC_API_URL_LAN || `http://192.168.1.50:${port}`;
      console.log('[API Config] Physical Android device detected:', url);
      return url;
    }
  } else if (Platform.OS === 'ios') {
    // Check if running on simulator
    const isSimulator = !Constants.isDevice;
    
    if (isSimulator) {
      // iOS simulator: use localhost
      const url = process.env.EXPO_PUBLIC_API_URL_IOS || `http://localhost:${port}`;
      console.log('[API Config] iOS Simulator detected:', url);
      return url;
    } else {
      // Physical iOS device: use LAN IP
      const url = process.env.EXPO_PUBLIC_API_URL_LAN || `http://192.168.1.50:${port}`;
      console.log('[API Config] Physical iOS device detected:', url);
      return url;
    }
  } else if (Platform.OS === 'web') {
    // Web: use localhost or deployed URL
    const url = process.env.EXPO_PUBLIC_API_URL_DEV || `http://localhost:${port}`;
    console.log('[API Config] Web platform detected:', url);
    return url;
  }

  // Fallback
  const fallback = process.env.EXPO_PUBLIC_API_URL_DEV || `http://localhost:${port}`;
  console.log('[API Config] Unknown platform, using fallback:', fallback);
  return fallback;
}

/**
 * Get platform-specific timeout (emulators vs physical devices)
 */
export function getPlatformTimeout(): number {
  const configTimeout = parseInt(process.env.EXPO_PUBLIC_API_TIMEOUT || '30000', 10);
  
  // Use configured timeout if valid
  if (configTimeout > 0) {
    return configTimeout;
  }

  // Default timeouts based on device type
  const isEmulatorLike = !Constants.isDevice || __DEV__;
  return isEmulatorLike ? 15000 : 45000;
}

/**
 * Get platform-specific retry attempts
 */
export function getPlatformRetryAttempts(): number {
  const isEmulatorLike = !Constants.isDevice || __DEV__;
  return isEmulatorLike ? 3 : 10;
}

/**
 * Log current platform configuration
 */
export function logPlatformInfo(): void {
  console.log('='.repeat(60));
  console.log('Platform API Configuration');
  console.log('='.repeat(60));
  console.log('Platform:', Platform.OS);
  console.log('Device Type:', Constants.isDevice ? 'Physical Device' : 'Emulator/Simulator');
  console.log('Device Name:', Constants.deviceName);
  console.log('Base URL:', resolveBaseURL());
  console.log('Timeout:', getPlatformTimeout() + 'ms');
  console.log('Retry Attempts:', getPlatformRetryAttempts());
  console.log('='.repeat(60));
}

/**
 * OneShot SDK client configuration and initialization with platform-aware settings
 */
import { OneShotClient } from 'oneshot-sdk';
import { getPlatformConfig, logPlatformConfig } from './platformConfig';

// Get platform-aware configuration
const platformConfig = getPlatformConfig();

// Log configuration in development
if (__DEV__) {
  logPlatformConfig();
}

// Create and export the configured SDK client with platform-aware settings
export const oneShotClient = new OneShotClient({
  baseUrl: platformConfig.apiUrl,
  timeout: platformConfig.timeout,
  retryAttempts: platformConfig.retryAttempts,
  retryDelay: 1000 // Progressive backoff will be applied automatically
});

// Configuration constants
export const CONFIG = {
  API_URL: platformConfig.apiUrl,
  API_TIMEOUT: platformConfig.timeout,
  RETRY_ATTEMPTS: platformConfig.retryAttempts,
  PLATFORM: platformConfig.platform,
  IS_EMULATOR: platformConfig.isEmulator,
  IS_PHYSICAL_DEVICE: platformConfig.isPhysicalDevice,
  POLLING_INTERVAL: 2000, // 2 seconds
  MAX_FILE_SIZE: 20 * 1024 * 1024, // 20MB
  ALLOWED_IMAGE_TYPES: ['image/jpeg', 'image/png', 'image/webp'],
  // Network diagnostics
  HEALTH_CHECK_TIMEOUT: 10000, // 10 seconds for health checks
  CONNECTION_RETRY_ATTEMPTS: 3,
  CONNECTION_RETRY_DELAY: 2000
} as const;

if (__DEV__) {
  // Helpful trace so developers can confirm which endpoint is being used
  // eslint-disable-next-line no-console
  console.info('[OneShot] SDK Configuration:');
  console.info('  API URL:', CONFIG.API_URL);
  console.info('  Timeout:', CONFIG.API_TIMEOUT + 'ms');
  console.info('  Retry Attempts:', CONFIG.RETRY_ATTEMPTS);
  console.info('  Platform:', CONFIG.PLATFORM);
  console.info('  Device Type:', CONFIG.IS_EMULATOR ? 'Emulator/Simulator' : 'Physical Device');
}

/**
 * Network diagnostic utilities
 */
export const NetworkDiagnostics = {
  /**
   * Test basic connectivity to the backend
   */
  async testConnectivity(): Promise<{
    success: boolean;
    latency?: number;
    error?: string;
  }> {
    const startTime = Date.now();
    
    try {
      const response = await oneShotClient.healthCheck();
      const latency = Date.now() - startTime;
      
      return {
        success: true,
        latency
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Connection test failed'
      };
    }
  },

  /**
   * Get detailed network information
   */
  getNetworkInfo() {
    return {
      apiUrl: CONFIG.API_URL,
      timeout: CONFIG.API_TIMEOUT,
      retryAttempts: 5,
      userAgent: navigator.userAgent,
      online: navigator.onLine
    };
  }
};

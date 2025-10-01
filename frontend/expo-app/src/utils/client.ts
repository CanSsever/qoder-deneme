/**
 * OneShot SDK client configuration and initialization
 */
import { OneShotClient } from 'oneshot-sdk';
import Constants from 'expo-constants';

// Get configuration from environment
const getApiUrl = (): string => {
  // In development, use the API_URL from app.json extra config
  // In production, this should come from your build configuration
  return Constants.expoConfig?.extra?.apiUrl || 'http://localhost:8000';
};

const getApiTimeout = (): number => {
  return Constants.expoConfig?.extra?.apiTimeout || 30000;
};

// Create and export the configured SDK client with enhanced mobile settings
export const oneShotClient = new OneShotClient({
  baseUrl: getApiUrl(),
  timeout: getApiTimeout(),
  retryAttempts: 5, // Increased for mobile scenarios
  retryDelay: 1000 // Progressive backoff will be applied automatically
});

// Configuration constants
export const CONFIG = {
  API_URL: getApiUrl(),
  API_TIMEOUT: getApiTimeout(),
  POLLING_INTERVAL: 2000, // 2 seconds
  MAX_FILE_SIZE: 20 * 1024 * 1024, // 20MB
  ALLOWED_IMAGE_TYPES: ['image/jpeg', 'image/png', 'image/webp'],
  // Network diagnostics
  HEALTH_CHECK_TIMEOUT: 10000, // 10 seconds for health checks
  CONNECTION_RETRY_ATTEMPTS: 3,
  CONNECTION_RETRY_DELAY: 2000
} as const;

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
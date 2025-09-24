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

// Create and export the configured SDK client
export const oneShotClient = new OneShotClient({
  baseUrl: getApiUrl(),
  timeout: getApiTimeout(),
  retryAttempts: 3,
  retryDelay: 1000
});

// Configuration constants
export const CONFIG = {
  API_URL: getApiUrl(),
  API_TIMEOUT: getApiTimeout(),
  POLLING_INTERVAL: 2000, // 2 seconds
  MAX_FILE_SIZE: 20 * 1024 * 1024, // 20MB
  ALLOWED_IMAGE_TYPES: ['image/jpeg', 'image/png', 'image/webp']
} as const;
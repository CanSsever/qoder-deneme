/**
 * Enhanced API client with timeout, retry, and exponential backoff
 * 
 * Features:
 * - Platform-aware base URL resolution
 * - Configurable timeouts (emulators: 15s, devices: 45s)
 * - Automatic retry with exponential backoff
 * - Request/response logging with timing
 * - Proper error handling
 */

// Note: This is a lightweight implementation for React Native
// For full axios support, install: npm install axios axios-retry
// Then uncomment the axios version below

interface RequestConfig {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  url: string;
  data?: any;
  headers?: Record<string, string>;
  timeout?: number;
}

interface ApiClientConfig {
  baseURL: string;
  timeout: number;
  retries: number;
}

class ApiClient {
  private config: ApiClientConfig;
  private authToken?: string;

  constructor(config: ApiClientConfig) {
    this.config = config;
  }

  /**
   * Set authentication token
   */
  setBearerToken(token: string): void {
    this.authToken = token;
  }

  /**
   * Clear authentication token
   */
  clearBearerToken(): void {
    this.authToken = undefined;
  }

  /**
   * Make HTTP request with retry logic
   */
  async request<T>(requestConfig: RequestConfig): Promise<T> {
    const { method, url, data, headers = {}, timeout = this.config.timeout } = requestConfig;
    const fullUrl = url.startsWith('http') ? url : `${this.config.baseURL}${url}`;
    
    // Add auth header if token exists
    const requestHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
      ...headers,
    };

    if (this.authToken) {
      requestHeaders['Authorization'] = `Bearer ${this.authToken}`;
    }

    let lastError: any;
    let attempt = 0;

    while (attempt < this.config.retries) {
      attempt++;
      const startTime = Date.now();

      try {
        // Create abort controller for timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        const response = await fetch(fullUrl, {
          method,
          headers: requestHeaders,
          body: data ? JSON.stringify(data) : undefined,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        const duration = Date.now() - startTime;
        console.log(`[API] ${method} ${url} ${response.status} ${duration}ms`);

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.message || errorData.detail || `HTTP ${response.status}`);
        }

        const result = await response.json();
        return result as T;

      } catch (error: any) {
        lastError = error;
        const duration = Date.now() - startTime;
        
        console.warn(
          `[API] ${method} ${url} FAILED (attempt ${attempt}/${this.config.retries}) ${duration}ms:`,
          error.message
        );

        // Don't retry on auth errors or client errors
        if (error.message?.includes('401') || error.message?.includes('403')) {
          throw error;
        }

        // Calculate backoff delay
        if (attempt < this.config.retries) {
          const backoffDelay = Math.min(1000 * Math.pow(2, attempt - 1), 8000);
          console.log(`[API] Retrying in ${backoffDelay}ms...`);
          await this.delay(backoffDelay);
        }
      }
    }

    // All retries exhausted
    throw new Error(
      lastError?.message || 'Request failed after multiple attempts'
    );
  }

  /**
   * GET request
   */
  async get<T>(url: string, headers?: Record<string, string>): Promise<T> {
    return this.request<T>({ method: 'GET', url, headers });
  }

  /**
   * POST request
   */
  async post<T>(url: string, data?: any, headers?: Record<string, string>): Promise<T> {
    return this.request<T>({ method: 'POST', url, data, headers });
  }

  /**
   * PUT request
   */
  async put<T>(url: string, data?: any, headers?: Record<string, string>): Promise<T> {
    return this.request<T>({ method: 'PUT', url, data, headers });
  }

  /**
   * DELETE request
   */
  async delete<T>(url: string, headers?: Record<string, string>): Promise<T> {
    return this.request<T>({ method: 'DELETE', url, headers });
  }

  /**
   * Delay helper
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export default ApiClient;


/* ========================================================================
 * AXIOS VERSION (Uncomment if axios is installed)
 * ======================================================================== */

/*
import axios, { AxiosInstance } from 'axios';
import axiosRetry from 'axios-retry';
import { resolveBaseURL } from '../config/api';

const isEmulatorLikely = __DEV__;
const TIMEOUT = isEmulatorLikely ? 15000 : 45000;

export const api: AxiosInstance = axios.create({
  baseURL: resolveBaseURL(),
  timeout: TIMEOUT,
});

// Configure retry logic
axiosRetry(api, {
  retries: 3,
  retryDelay: (retryCount) => {
    const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 8000);
    console.log(`[API] Retry attempt ${retryCount} in ${delay}ms`);
    return delay;
  },
  retryCondition: (error) => {
    const status = error?.response?.status;
    // Retry on network errors, timeouts, or 5xx errors
    return !status || status >= 500 || status === 408 || status === 429;
  },
});

// Request interceptor for timing
api.interceptors.request.use((config) => {
  (config as any).__startTime = Date.now();
  return config;
});

// Response interceptor for logging
api.interceptors.response.use(
  (response) => {
    const duration = Date.now() - ((response.config as any).__startTime || Date.now());
    console.log(
      `[API] ${response.config.method?.toUpperCase()} ${response.config.url} ${response.status} ${duration}ms`
    );
    return response;
  },
  (error) => {
    const config: any = error.config || {};
    const duration = Date.now() - (config.__startTime || Date.now());
    console.warn(
      `[API] ${config?.method?.toUpperCase()} ${config?.url} FAIL ${duration}ms:`,
      error?.message
    );
    return Promise.reject(error);
  }
);

export default api;
*/

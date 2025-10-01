/**
 * Enhanced HTTP Client with adaptive timeout, retry logic, and circuit breaker
 */
import {
  HttpClient,
  RequestOptions,
  NetworkError,
  AuthenticationError,
  ValidationError,
  RateLimitError,
  PaymentRequiredError,
  OneShotError,
  ErrorCode
} from './types';
import { NetworkQualityAssessment, NetworkQuality, ConnectionAssessment } from './network-quality';
import { CircuitBreaker, CircuitBreakerError, circuitBreakerManager } from './circuit-breaker';

export class FetchHttpClient implements HttpClient {
  private baseUrl: string;
  private defaultTimeout: number;
  private defaultRetryAttempts: number;
  private defaultRetryDelay: number;
  private bearerToken?: string;
  private networkAssessment: NetworkQualityAssessment;
  private circuitBreaker: CircuitBreaker;
  private lastNetworkAssessment?: ConnectionAssessment;
  private assessmentCacheTime: number = 30000; // 30 seconds

  constructor(
    baseUrl: string,
    timeout = 30000,
    retryAttempts = 5,
    retryDelay = 1000
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, ''); // Remove trailing slash
    this.defaultTimeout = timeout;
    this.defaultRetryAttempts = retryAttempts;
    this.defaultRetryDelay = retryDelay;
    
    // Initialize network quality assessment
    this.networkAssessment = new NetworkQualityAssessment(baseUrl);
    
    // Initialize circuit breaker for HTTP client
    this.circuitBreaker = circuitBreakerManager.getBreaker('http-client', {
      failureThreshold: 5,
      recoveryTimeout: 30000,
      successThreshold: 3,
      monitoringWindow: 60000
    });
  }

  setBearerToken(token: string): void {
    this.bearerToken = token;
  }

  clearBearerToken(): void {
    this.bearerToken = undefined;
  }

  async get<T>(url: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('GET', url, undefined, options);
  }

  async post<T>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('POST', url, data, options);
  }

  async put<T>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('PUT', url, data, options);
  }

  async delete<T>(url: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('DELETE', url, undefined, options);
  }

  private async request<T>(
    method: string,
    url: string,
    data?: any,
    options?: RequestOptions
  ): Promise<T> {
    // Get adaptive network settings
    const networkSettings = await this.getAdaptiveNetworkSettings();
    
    const fullUrl = url.startsWith('http') ? url : `${this.baseUrl}${url}`;
    const timeout = options?.timeout ?? networkSettings.recommendedTimeout;
    const retryAttempts = options?.retryAttempts ?? networkSettings.maxRetries;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...options?.headers
    };

    // Add Authorization header if token is available
    if (this.bearerToken) {
      headers.Authorization = `Bearer ${this.bearerToken}`;
    }

    // Add idempotency key if provided
    if (options?.idempotencyKey) {
      headers['Idempotency-Key'] = options.idempotencyKey;
    }

    // Create AbortController for timeout (manual implementation for React Native compatibility)
    let controller: AbortController | null = null;
    let timeoutId: NodeJS.Timeout | null = null;
    
    const requestConfig: RequestInit = {
      method,
      headers
    };

    // Always use manual timeout implementation for React Native compatibility
    controller = new AbortController();
    requestConfig.signal = controller.signal;
    timeoutId = setTimeout(() => {
      if (controller) {
        controller.abort();
      }
    }, timeout);

    if (data && (method === 'POST' || method === 'PUT')) {
      requestConfig.body = JSON.stringify(data);
    }

    try {
      // Execute request through circuit breaker
      const result = await this.circuitBreaker.execute(async () => {
        return this.executeWithAdaptiveRetry<T>(
          fullUrl, 
          requestConfig, 
          retryAttempts, 
          networkSettings
        );
      });
      
      // Clear timeout if request succeeds
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      return result;
    } catch (error) {
      // Clear timeout if request fails
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      
      // Handle circuit breaker errors specially
      if (error instanceof CircuitBreakerError) {
        throw new NetworkError(
          `Service temporarily unavailable: ${error.message}. Circuit breaker is ${error.circuitState}.`
        );
      }
      
      throw error;
    }
  }

  /**
   * Get adaptive network settings based on current conditions
   */
  private async getAdaptiveNetworkSettings(): Promise<ConnectionAssessment> {
    // Return cached assessment if still fresh
    if (this.lastNetworkAssessment && 
        Date.now() - this.lastNetworkAssessment.metrics.timestamp < this.assessmentCacheTime) {
      return this.lastNetworkAssessment;
    }

    try {
      // Perform fresh network assessment
      this.lastNetworkAssessment = await this.networkAssessment.assessNetworkQuality();
      console.log('Network assessment completed:', {
        quality: this.lastNetworkAssessment.quality,
        latency: this.lastNetworkAssessment.metrics.latency,
        timeout: this.lastNetworkAssessment.recommendedTimeout,
        retries: this.lastNetworkAssessment.maxRetries
      });
      
      return this.lastNetworkAssessment;
    } catch (error) {
      console.warn('Network assessment failed, using fallback settings:', error);
      
      // Return conservative fallback settings
      return {
        quality: NetworkQuality.POOR,
        metrics: {
          latency: 2000,
          bandwidth: 64,
          stability: 50,
          errorRate: 20,
          timestamp: Date.now()
        },
        recommendedTimeout: 60000,
        maxRetries: 10,
        backoffStrategy: {
          type: 'conservative',
          baseDelay: 3000,
          maxDelay: 30000,
          multiplier: 2
        }
      };
    }
  }

  private async executeWithAdaptiveRetry<T>(
    url: string,
    config: RequestInit,
    retriesLeft: number,
    networkSettings: ConnectionAssessment
  ): Promise<T> {
    const attemptNumber = networkSettings.maxRetries - retriesLeft + 1;
    const { backoffStrategy } = networkSettings;
    
    try {
      const response = await fetch(url, config);
      return await this.handleResponse<T>(response);
    } catch (error: any) {
      // Check if this is a timeout error
      if (config.signal && config.signal.aborted) {
        error = new Error('Request timeout');
        error.name = 'AbortError';
      }
      
      if (this.shouldRetry(error, retriesLeft)) {
        // Calculate adaptive backoff delay
        const backoffDelay = this.calculateBackoffDelay(
          attemptNumber,
          backoffStrategy
        );
        
        console.warn(`Request failed, retrying in ${backoffDelay}ms`, {
          url,
          error: error.message,
          attemptNumber,
          retriesLeft,
          networkQuality: networkSettings.quality,
          backoffStrategy: backoffStrategy.type
        });
        
        await this.delay(backoffDelay);
        return this.executeWithAdaptiveRetry<T>(url, config, retriesLeft - 1, networkSettings);
      }
      throw this.normalizeError(error);
    }
  }

  /**
   * Calculate backoff delay based on strategy and attempt number
   */
  private calculateBackoffDelay(
    attemptNumber: number,
    strategy: ConnectionAssessment['backoffStrategy']
  ): number {
    let delay: number;
    
    switch (strategy.type) {
      case 'linear':
        delay = strategy.baseDelay * attemptNumber;
        break;
        
      case 'exponential':
        delay = strategy.baseDelay * Math.pow(strategy.multiplier, attemptNumber - 1);
        break;
        
      case 'extended':
        // Custom extended backoff: 2s, 4s, 6s, 8s, 12s, 16s, 20s
        const extendedDelays = [2000, 4000, 6000, 8000, 12000, 16000, 20000];
        delay = extendedDelays[Math.min(attemptNumber - 1, extendedDelays.length - 1)] || strategy.maxDelay;
        break;
        
      case 'conservative':
        // Conservative backoff: 3s, 5s, 7s, 10s, 15s, 20s, 25s, 30s
        const conservativeDelays = [3000, 5000, 7000, 10000, 15000, 20000, 25000, 30000];
        delay = conservativeDelays[Math.min(attemptNumber - 1, conservativeDelays.length - 1)] || strategy.maxDelay;
        break;
        
      default:
        delay = strategy.baseDelay * Math.pow(2, attemptNumber - 1);
    }
    
    // Ensure delay doesn't exceed maximum
    return Math.min(delay, strategy.maxDelay);
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    let data: any;
    
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw this.createErrorFromResponse(response, data);
    }

    return data as T;
  }

  private createErrorFromResponse(response: Response, data: any): OneShotError {
    const message = data?.error?.message || data?.detail || data?.message || 'Request failed';
    const code = data?.error?.code || data?.error_code || 'UNKNOWN_ERROR';
    
    switch (response.status) {
      case 401:
        return new AuthenticationError(message);
      case 402:
        return new PaymentRequiredError(message);
      case 422:
        return new ValidationError(message, data?.error?.details || data?.details);
      case 429:
        return new RateLimitError(message);
      default:
        return new OneShotError(code, message, response.status, data);
    }
  }

  private shouldRetry(error: any, retriesLeft: number): boolean {
    if (retriesLeft <= 0) return false;

    // Retry on network errors, timeouts, and 5xx server errors
    if (error instanceof NetworkError) return true;
    if (error.name === 'AbortError') return true; // Timeout
    if (error instanceof OneShotError && error.statusCode && error.statusCode >= 500) {
      return true;
    }

    return false;
  }

  private normalizeError(error: any): OneShotError {
    if (error instanceof OneShotError) {
      return error;
    }

    // Check for timeout errors with more detailed messages
    if (error.name === 'AbortError' || 
        (error.message && (error.message.includes('timeout') || error.message.includes('aborted')))) {
      return new NetworkError('Connection timeout. Please check your network connection and try again.');
    }

    // Check for network connectivity issues
    if (error instanceof TypeError && error.message.includes('fetch')) {
      return new NetworkError('Unable to reach server. Please check your internet connection.');
    }

    // Check for specific network errors
    if (error.message && error.message.includes('Failed to fetch')) {
      return new NetworkError('Network request failed. Please check your connection to the server.');
    }

    return new OneShotError(ErrorCode.NETWORK_ERROR, error.message || 'Unknown network error');
  }

  private async delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Get current network quality assessment
   */
  async getNetworkQuality(): Promise<ConnectionAssessment> {
    return this.getAdaptiveNetworkSettings();
  }

  /**
   * Force refresh network assessment
   */
  async refreshNetworkAssessment(): Promise<ConnectionAssessment> {
    this.lastNetworkAssessment = undefined;
    return this.getAdaptiveNetworkSettings();
  }

  /**
   * Get circuit breaker metrics
   */
  getCircuitBreakerMetrics() {
    return this.circuitBreaker.getMetrics();
  }

  /**
   * Reset circuit breaker (for testing or recovery)
   */
  resetCircuitBreaker(): void {
    this.circuitBreaker.forceReset();
  }

  /**
   * Get network diagnostics information
   */
  async getNetworkDiagnostics(): Promise<{
    networkQuality: ConnectionAssessment;
    circuitBreaker: any;
    lastErrors: string[];
  }> {
    const networkQuality = await this.getNetworkQuality();
    const circuitMetrics = this.getCircuitBreakerMetrics();
    
    return {
      networkQuality,
      circuitBreaker: {
        state: circuitMetrics.state,
        uptime: circuitMetrics.uptime,
        totalRequests: circuitMetrics.totalRequests,
        totalFailures: circuitMetrics.totalFailures,
        description: this.circuitBreaker.getStateDescription()
      },
      lastErrors: [] // Could be enhanced to track recent errors
    };
  }
}
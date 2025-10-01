/**
 * HTTP Client with retry logic and error handling
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

export class FetchHttpClient implements HttpClient {
  private baseUrl: string;
  private defaultTimeout: number;
  private defaultRetryAttempts: number;
  private defaultRetryDelay: number;
  private bearerToken?: string;

  constructor(
    baseUrl: string,
    timeout = 30000,
    retryAttempts = 5, // Increased for mobile scenarios
    retryDelay = 1000
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, ''); // Remove trailing slash
    this.defaultTimeout = timeout;
    this.defaultRetryAttempts = retryAttempts;
    this.defaultRetryDelay = retryDelay;
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
    const fullUrl = url.startsWith('http') ? url : `${this.baseUrl}${url}`;
    const timeout = options?.timeout ?? this.defaultTimeout;
    const retryAttempts = options?.retryAttempts ?? this.defaultRetryAttempts;

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
      const result = await this.executeWithRetry<T>(fullUrl, requestConfig, retryAttempts);
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
      throw error;
    }
  }

  private async executeWithRetry<T>(
    url: string,
    config: RequestInit,
    retriesLeft: number
  ): Promise<T> {
    const attemptNumber = this.defaultRetryAttempts - retriesLeft + 1;
    
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
        // Progressive backoff: 1s, 2s, 4s, 8s, 16s
        const backoffDelay = this.defaultRetryDelay * Math.pow(2, attemptNumber - 1);
        console.warn(`Request failed, retrying in ${backoffDelay}ms (attempt ${attemptNumber}/${this.defaultRetryAttempts})`, {
          url,
          error: error.message,
          attemptNumber,
          retriesLeft
        });
        
        await this.delay(backoffDelay);
        return this.executeWithRetry<T>(url, config, retriesLeft - 1);
      }
      throw this.normalizeError(error);
    }
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
}
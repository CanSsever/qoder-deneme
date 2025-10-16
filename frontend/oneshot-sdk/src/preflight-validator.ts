/**
 * Pre-flight Connection Validator
 * Verifies backend availability before critical operations
 */

import { NetworkQualityAssessment, NetworkQuality } from './network-quality';

export enum ConnectionStatus {
  CONNECTED = 'connected',
  CHECKING = 'checking',
  DISCONNECTED = 'disconnected',
  DEGRADED = 'degraded',
  UNKNOWN = 'unknown'
}

export interface PreflightResult {
  status: ConnectionStatus;
  latency?: number;
  timestamp: number;
  error?: string;
  backendReachable: boolean;
  quality?: NetworkQuality;
  recommendation?: string;
}

export interface PreflightOptions {
  timeout?: number;
  healthEndpoint?: string;
  retryOnFailure?: boolean;
  retryAttempts?: number;
}

export class PreflightValidator {
  private baseUrl: string;
  private networkAssessment: NetworkQualityAssessment;
  private lastResult?: PreflightResult;
  private listeners: Set<(result: PreflightResult) => void> = new Set();

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.networkAssessment = new NetworkQualityAssessment(baseUrl);
  }

  /**
   * Perform pre-flight connection validation
   */
  async validate(options?: PreflightOptions): Promise<PreflightResult> {
    const {
      timeout = 5000,
      healthEndpoint = '/healthz',
      retryOnFailure = false,
      retryAttempts = 2
    } = options || {};

    // Notify listeners that validation is starting
    this.notifyListeners({
      status: ConnectionStatus.CHECKING,
      timestamp: Date.now(),
      backendReachable: false
    });

    let lastError: any;
    const maxAttempts = retryOnFailure ? retryAttempts : 1;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const result = await this.performHealthCheck(healthEndpoint, timeout);
        this.lastResult = result;
        this.notifyListeners(result);
        return result;
      } catch (error: any) {
        lastError = error;
        
        if (attempt < maxAttempts - 1) {
          // Wait before retry with exponential backoff
          const delay = Math.min(1000 * Math.pow(2, attempt), 5000);
          await this.delay(delay);
        }
      }
    }

    // All attempts failed
    const failureResult = this.createFailureResult(lastError);
    this.lastResult = failureResult;
    this.notifyListeners(failureResult);
    return failureResult;
  }

  /**
   * Perform health check against backend
   */
  private async performHealthCheck(endpoint: string, timeout: number): Promise<PreflightResult> {
    const startTime = performance.now();
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'GET',
        signal: controller.signal,
        headers: {
          'Cache-Control': 'no-cache'
        }
      });

      clearTimeout(timeoutId);
      const latency = Math.round(performance.now() - startTime);

      if (!response.ok) {
        return {
          status: ConnectionStatus.DISCONNECTED,
          latency,
          timestamp: Date.now(),
          backendReachable: false,
          error: `Health check failed with status ${response.status}`,
          recommendation: 'Backend is running but returned an error. Check backend logs.'
        };
      }

      // Assess connection quality based on latency
      const status = this.assessConnectionStatus(latency);
      const quality = this.latencyToQuality(latency);

      return {
        status,
        latency,
        timestamp: Date.now(),
        backendReachable: true,
        quality,
        recommendation: this.getRecommendation(status, latency)
      };
    } catch (error: any) {
      clearTimeout(timeoutId);
      const latency = Math.round(performance.now() - startTime);
      
      throw {
        message: error.message,
        name: error.name,
        latency
      };
    }
  }

  /**
   * Assess connection status based on latency
   */
  private assessConnectionStatus(latency: number): ConnectionStatus {
    if (latency < 100) {
      return ConnectionStatus.CONNECTED;
    } else if (latency < 500) {
      return ConnectionStatus.CONNECTED;
    } else if (latency < 2000) {
      return ConnectionStatus.DEGRADED;
    } else {
      return ConnectionStatus.DEGRADED;
    }
  }

  /**
   * Convert latency to network quality
   */
  private latencyToQuality(latency: number): NetworkQuality {
    if (latency < 100) {
      return NetworkQuality.EXCELLENT;
    } else if (latency < 300) {
      return NetworkQuality.GOOD;
    } else if (latency < 800) {
      return NetworkQuality.FAIR;
    } else {
      return NetworkQuality.POOR;
    }
  }

  /**
   * Get user-facing recommendation based on connection status
   */
  private getRecommendation(status: ConnectionStatus, latency: number): string {
    switch (status) {
      case ConnectionStatus.CONNECTED:
        if (latency < 100) {
          return 'Excellent connection quality';
        } else if (latency < 500) {
          return 'Good connection quality';
        } else {
          return 'Connection is slower than optimal';
        }
      case ConnectionStatus.DEGRADED:
        return 'Connection is slow. Consider switching to a faster network.';
      case ConnectionStatus.DISCONNECTED:
        return 'Cannot reach backend. Check if server is running.';
      default:
        return 'Connection status unknown';
    }
  }

  /**
   * Create failure result from error
   */
  private createFailureResult(error: any): PreflightResult {
    const errorMessage = error?.message || 'Unknown error';
    let recommendation = 'Cannot connect to backend.';
    
    if (errorMessage.includes('aborted') || errorMessage.includes('timeout')) {
      recommendation = 'Connection timeout. Server may be down or network is very slow.';
    } else if (errorMessage.includes('Failed to fetch') || errorMessage.includes('Network request failed')) {
      recommendation = 'Network error. Check if backend is running and accessible.';
    } else if (errorMessage.includes('ECONNREFUSED')) {
      recommendation = 'Connection refused. Backend server is not running on the configured address.';
    }

    return {
      status: ConnectionStatus.DISCONNECTED,
      latency: error?.latency,
      timestamp: Date.now(),
      backendReachable: false,
      error: errorMessage,
      recommendation
    };
  }

  /**
   * Get last validation result
   */
  getLastResult(): PreflightResult | undefined {
    return this.lastResult;
  }

  /**
   * Check if backend is currently reachable based on last result
   */
  isBackendReachable(): boolean {
    return this.lastResult?.backendReachable || false;
  }

  /**
   * Add listener for validation status changes
   */
  addListener(listener: (result: PreflightResult) => void): void {
    this.listeners.add(listener);
  }

  /**
   * Remove listener
   */
  removeListener(listener: (result: PreflightResult) => void): void {
    this.listeners.delete(listener);
  }

  /**
   * Notify all listeners of result change
   */
  private notifyListeners(result: PreflightResult): void {
    for (const listener of this.listeners) {
      try {
        listener(result);
      } catch (error) {
        console.warn('Error notifying preflight listener:', error);
      }
    }
  }

  /**
   * Quick check without retries (for polling scenarios)
   */
  async quickCheck(): Promise<PreflightResult> {
    return this.validate({
      timeout: 3000,
      retryOnFailure: false
    });
  }

  /**
   * Comprehensive check with retries and network quality assessment
   */
  async comprehensiveCheck(): Promise<{
    preflight: PreflightResult;
    networkQuality: any;
  }> {
    const [preflight, networkQuality] = await Promise.all([
      this.validate({
        timeout: 5000,
        retryOnFailure: true,
        retryAttempts: 3
      }),
      this.networkAssessment.assessNetworkQuality().catch(() => null)
    ]);

    return {
      preflight,
      networkQuality
    };
  }

  /**
   * Reset validator state
   */
  reset(): void {
    this.lastResult = undefined;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * Network Quality Assessment Framework
 * Implements dynamic network quality monitoring and assessment for adaptive timeout management
 */

export interface NetworkQualityMetrics {
  latency: number;
  bandwidth: number;
  stability: number;
  errorRate: number;
  timestamp: number;
}

export interface ConnectionAssessment {
  quality: NetworkQuality;
  metrics: NetworkQualityMetrics;
  recommendedTimeout: number;
  maxRetries: number;
  backoffStrategy: BackoffStrategy;
}

export enum NetworkQuality {
  EXCELLENT = 'excellent',
  GOOD = 'good', 
  FAIR = 'fair',
  POOR = 'poor'
}

export interface BackoffStrategy {
  type: 'linear' | 'exponential' | 'extended' | 'conservative';
  baseDelay: number;
  maxDelay: number;
  multiplier: number;
}

export interface HealthCheckResult {
  success: boolean;
  latency: number;
  timestamp: number;
  error?: string;
}

export interface BandwidthTestResult {
  bandwidth: number; // Kbps
  testDuration: number;
  bytesTransferred: number;
}

export class NetworkQualityAssessment {
  private static readonly LATENCY_HISTORY_SIZE = 10;
  private static readonly ERROR_HISTORY_SIZE = 20;
  private static readonly BANDWIDTH_TEST_SIZE = 1024; // 1KB test payload
  
  private latencyHistory: number[] = [];
  private errorHistory: boolean[] = [];
  private lastAssessment?: ConnectionAssessment;
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  /**
   * Perform comprehensive network quality assessment
   */
  async assessNetworkQuality(): Promise<ConnectionAssessment> {
    try {
      // Run parallel tests for faster assessment
      const [healthResult, bandwidthResult, stabilityResult] = await Promise.all([
        this.measureLatency(),
        this.estimateBandwidth(),
        this.measureStability()
      ]);

      const metrics: NetworkQualityMetrics = {
        latency: healthResult.latency,
        bandwidth: bandwidthResult.bandwidth,
        stability: stabilityResult,
        errorRate: this.calculateErrorRate(),
        timestamp: Date.now()
      };

      const quality = this.classifyNetworkQuality(metrics);
      const assessment: ConnectionAssessment = {
        quality,
        metrics,
        recommendedTimeout: this.calculateRecommendedTimeout(quality, metrics),
        maxRetries: this.calculateMaxRetries(quality),
        backoffStrategy: this.getBackoffStrategy(quality)
      };

      this.lastAssessment = assessment;
      return assessment;
    } catch (error) {
      // Fallback to conservative assessment on error
      return this.getFallbackAssessment();
    }
  }

  /**
   * Get cached assessment or perform new one if stale
   */
  async getCachedOrFreshAssessment(maxAge: number = 30000): Promise<ConnectionAssessment> {
    if (this.lastAssessment && 
        Date.now() - this.lastAssessment.metrics.timestamp < maxAge) {
      return this.lastAssessment;
    }
    return this.assessNetworkQuality();
  }

  /**
   * Quick latency check using health endpoint
   */
  async measureLatency(): Promise<HealthCheckResult> {
    const startTime = performance.now();
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      const response = await fetch(`${this.baseUrl}/healthz`, {
        method: 'GET',
        signal: controller.signal,
        headers: {
          'Cache-Control': 'no-cache'
        }
      });

      clearTimeout(timeoutId);
      const latency = Math.round(performance.now() - startTime);
      
      this.updateLatencyHistory(latency);

      return {
        success: response.ok,
        latency,
        timestamp: Date.now()
      };
    } catch (error: any) {
      const latency = Math.round(performance.now() - startTime);
      this.updateLatencyHistory(latency);
      this.updateErrorHistory(true);

      return {
        success: false,
        latency,
        timestamp: Date.now(),
        error: error.message
      };
    }
  }

  /**
   * Estimate bandwidth using small payload test
   */
  async estimateBandwidth(): Promise<BandwidthTestResult> {
    const testPayload = 'x'.repeat(NetworkQualityAssessment.BANDWIDTH_TEST_SIZE);
    const startTime = performance.now();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(`${this.baseUrl}/healthz`, {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache'
        },
        body: JSON.stringify({ test: testPayload })
      });

      clearTimeout(timeoutId);
      const duration = performance.now() - startTime;
      const bandwidth = Math.round((NetworkQualityAssessment.BANDWIDTH_TEST_SIZE * 8) / (duration / 1000)); // bits per second to Kbps

      return {
        bandwidth: Math.max(bandwidth, 1), // Minimum 1 Kbps
        testDuration: duration,
        bytesTransferred: NetworkQualityAssessment.BANDWIDTH_TEST_SIZE
      };
    } catch (error) {
      // Return conservative bandwidth estimate on error
      return {
        bandwidth: 64, // 64 Kbps fallback
        testDuration: 5000,
        bytesTransferred: 0
      };
    }
  }

  /**
   * Measure connection stability over multiple quick requests
   */
  async measureStability(): Promise<number> {
    const testCount = 5;
    const results: boolean[] = [];

    const promises = Array(testCount).fill(0).map(async (_, index) => {
      try {
        await new Promise(resolve => setTimeout(resolve, index * 100)); // Stagger requests
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000);

        const response = await fetch(`${this.baseUrl}/healthz`, {
          method: 'HEAD',
          signal: controller.signal,
          headers: {
            'Cache-Control': 'no-cache'
          }
        });

        clearTimeout(timeoutId);
        return response.ok;
      } catch {
        return false;
      }
    });

    const testResults = await Promise.all(promises);
    const successCount = testResults.filter(success => success).length;
    const stability = (successCount / testCount) * 100;

    // Update error history with overall test result
    this.updateErrorHistory(stability < 80);

    return stability;
  }

  /**
   * Calculate error rate from recent history
   */
  private calculateErrorRate(): number {
    if (this.errorHistory.length === 0) return 0;
    
    const errorCount = this.errorHistory.filter(error => error).length;
    return (errorCount / this.errorHistory.length) * 100;
  }

  /**
   * Classify network quality based on metrics
   */
  private classifyNetworkQuality(metrics: NetworkQualityMetrics): NetworkQuality {
    const { latency, bandwidth, stability, errorRate } = metrics;

    // Excellent: Low latency, high bandwidth, stable, low error rate
    if (latency < 100 && bandwidth > 1000 && stability > 95 && errorRate < 1) {
      return NetworkQuality.EXCELLENT;
    }

    // Good: Moderate latency, decent bandwidth, mostly stable
    if (latency < 300 && bandwidth > 256 && stability > 85 && errorRate < 5) {
      return NetworkQuality.GOOD;
    }

    // Fair: Higher latency but still usable
    if (latency < 800 && bandwidth > 64 && stability > 70 && errorRate < 15) {
      return NetworkQuality.FAIR;
    }

    // Poor: High latency, low bandwidth, or unstable
    return NetworkQuality.POOR;
  }

  /**
   * Calculate recommended timeout based on network quality and metrics
   */
  private calculateRecommendedTimeout(quality: NetworkQuality, metrics: NetworkQualityMetrics): number {
    const baseTimeouts = {
      [NetworkQuality.EXCELLENT]: 15000,
      [NetworkQuality.GOOD]: 30000,
      [NetworkQuality.FAIR]: 45000,
      [NetworkQuality.POOR]: 60000
    };

    let timeout = baseTimeouts[quality];

    // Adjust based on actual latency
    if (metrics.latency > 1000) {
      timeout += metrics.latency * 2; // Add buffer for high latency
    }

    // Adjust based on stability
    if (metrics.stability < 80) {
      timeout = Math.round(timeout * 1.5); // Increase timeout for unstable connections
    }

    return Math.min(timeout, 120000); // Cap at 2 minutes
  }

  /**
   * Calculate maximum retry attempts based on network quality
   */
  private calculateMaxRetries(quality: NetworkQuality): number {
    const retryLimits = {
      [NetworkQuality.EXCELLENT]: 3,
      [NetworkQuality.GOOD]: 5,
      [NetworkQuality.FAIR]: 7,
      [NetworkQuality.POOR]: 10
    };

    return retryLimits[quality];
  }

  /**
   * Get appropriate backoff strategy for network quality
   */
  private getBackoffStrategy(quality: NetworkQuality): BackoffStrategy {
    const strategies = {
      [NetworkQuality.EXCELLENT]: {
        type: 'linear' as const,
        baseDelay: 1000,
        maxDelay: 5000,
        multiplier: 1
      },
      [NetworkQuality.GOOD]: {
        type: 'exponential' as const,
        baseDelay: 1000,
        maxDelay: 16000,
        multiplier: 2
      },
      [NetworkQuality.FAIR]: {
        type: 'extended' as const,
        baseDelay: 2000,
        maxDelay: 20000,
        multiplier: 1.5
      },
      [NetworkQuality.POOR]: {
        type: 'conservative' as const,
        baseDelay: 3000,
        maxDelay: 30000,
        multiplier: 1.8
      }
    };

    return strategies[quality];
  }

  /**
   * Get fallback assessment for error conditions
   */
  private getFallbackAssessment(): ConnectionAssessment {
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

  /**
   * Update latency history for trend analysis
   */
  private updateLatencyHistory(latency: number): void {
    this.latencyHistory.push(latency);
    if (this.latencyHistory.length > NetworkQualityAssessment.LATENCY_HISTORY_SIZE) {
      this.latencyHistory.shift();
    }
  }

  /**
   * Update error history for error rate calculation
   */
  private updateErrorHistory(isError: boolean): void {
    this.errorHistory.push(isError);
    if (this.errorHistory.length > NetworkQualityAssessment.ERROR_HISTORY_SIZE) {
      this.errorHistory.shift();
    }
  }

  /**
   * Get average latency from recent history
   */
  getAverageLatency(): number {
    if (this.latencyHistory.length === 0) return 1000; // Default fallback
    return Math.round(this.latencyHistory.reduce((sum, latency) => sum + latency, 0) / this.latencyHistory.length);
  }

  /**
   * Get network quality assessment as human-readable string
   */
  getQualityDescription(quality: NetworkQuality): string {
    const descriptions = {
      [NetworkQuality.EXCELLENT]: 'Excellent connection - fast and stable',
      [NetworkQuality.GOOD]: 'Good connection - reliable performance',
      [NetworkQuality.FAIR]: 'Fair connection - may experience delays',
      [NetworkQuality.POOR]: 'Poor connection - slow or unstable'
    };

    return descriptions[quality];
  }

  /**
   * Reset all collected metrics and history
   */
  reset(): void {
    this.latencyHistory = [];
    this.errorHistory = [];
    this.lastAssessment = undefined;
  }
}
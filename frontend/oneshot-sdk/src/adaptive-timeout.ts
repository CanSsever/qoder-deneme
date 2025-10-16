/**
 * Adaptive Timeout Calibration
 * Dynamically adjusts timeouts based on observed network performance
 */

import { NetworkQuality } from './network-quality';

export interface TimeoutCalibrationConfig {
  minTimeout: number;
  maxTimeout: number;
  platformDefault: number;
  smoothingFactor: number; // 0-1, how much to weight new observations
  persistenceEnabled: boolean;
}

export interface CalibrationData {
  currentTimeout: number;
  observedLatencies: number[];
  averageLatency: number;
  p95Latency: number;
  successRate: number;
  lastCalibration: number;
  networkSSID?: string;
}

export interface RequestMetrics {
  duration: number;
  success: boolean;
  timestamp: number;
}

export class AdaptiveTimeoutCalibrator {
  private config: TimeoutCalibrationConfig;
  private requestHistory: RequestMetrics[] = [];
  private currentTimeout: number;
  private maxHistorySize = 50;
  private storageKey = '@oneshot_timeout_calibration';
  private lastNetworkSSID?: string;

  constructor(config?: Partial<TimeoutCalibrationConfig>) {
    this.config = {
      minTimeout: 5000,      // 5 seconds minimum
      maxTimeout: 120000,    // 2 minutes maximum
      platformDefault: 30000, // 30 seconds default
      smoothingFactor: 0.3,   // 30% weight to new observations
      persistenceEnabled: true,
      ...config
    };

    this.currentTimeout = this.config.platformDefault;
    this.loadCalibration();
  }

  /**
   * Record request metrics for calibration
   */
  recordRequest(metrics: RequestMetrics): void {
    this.requestHistory.push(metrics);

    // Limit history size
    if (this.requestHistory.length > this.maxHistorySize) {
      this.requestHistory = this.requestHistory.slice(-this.maxHistorySize);
    }

    // Trigger recalibration after every 5 requests
    if (this.requestHistory.length % 5 === 0) {
      this.recalibrate();
    }
  }

  /**
   * Recalibrate timeout based on observed performance
   */
  recalibrate(): void {
    if (this.requestHistory.length === 0) {
      return;
    }

    const recentRequests = this.requestHistory.slice(-20); // Last 20 requests
    const latencies = recentRequests.map(r => r.duration);
    const successCount = recentRequests.filter(r => r.success).length;
    const successRate = successCount / recentRequests.length;

    // Calculate statistics
    const avgLatency = this.calculateAverage(latencies);
    const p95Latency = this.calculatePercentile(latencies, 95);

    // Calculate new timeout
    let newTimeout = this.calculateOptimalTimeout(avgLatency, p95Latency, successRate);

    // Apply smoothing
    newTimeout = this.applySmoothing(this.currentTimeout, newTimeout);

    // Enforce bounds
    newTimeout = Math.max(this.config.minTimeout, Math.min(this.config.maxTimeout, newTimeout));

    // Update current timeout
    this.currentTimeout = Math.round(newTimeout);

    // Persist calibration
    if (this.config.persistenceEnabled) {
      this.saveCalibration();
    }

    console.log('Timeout recalibrated:', {
      oldTimeout: this.currentTimeout,
      newTimeout: this.currentTimeout,
      avgLatency: Math.round(avgLatency),
      p95Latency: Math.round(p95Latency),
      successRate: (successRate * 100).toFixed(1) + '%'
    });
  }

  /**
   * Calculate optimal timeout based on performance metrics
   */
  private calculateOptimalTimeout(
    avgLatency: number,
    p95Latency: number,
    successRate: number
  ): number {
    // Base timeout on P95 latency with buffer
    let timeout = p95Latency * 1.5;

    // Adjust based on success rate
    if (successRate < 0.8) {
      // Low success rate: increase timeout significantly
      timeout = p95Latency * 2.5;
    } else if (successRate < 0.9) {
      // Moderate success rate: increase timeout moderately
      timeout = p95Latency * 2.0;
    }

    // Check if requests are approaching current timeout
    if (avgLatency > this.currentTimeout * 0.8) {
      // Requests approaching timeout: increase it
      timeout = Math.max(timeout, avgLatency * 1.5);
    }

    // Check if requests complete well within timeout
    if (avgLatency < this.currentTimeout * 0.3 && successRate > 0.95) {
      // Requests completing quickly: can reduce timeout
      timeout = Math.min(timeout, avgLatency * 3);
    }

    return timeout;
  }

  /**
   * Apply exponential smoothing to avoid abrupt changes
   */
  private applySmoothing(current: number, target: number): number {
    const alpha = this.config.smoothingFactor;
    return current * (1 - alpha) + target * alpha;
  }

  /**
   * Calculate average of values
   */
  private calculateAverage(values: number[]): number {
    if (values.length === 0) return 0;
    return values.reduce((sum, val) => sum + val, 0) / values.length;
  }

  /**
   * Calculate percentile of values
   */
  private calculatePercentile(values: number[], percentile: number): number {
    if (values.length === 0) return 0;
    
    const sorted = [...values].sort((a, b) => a - b);
    const index = Math.ceil((percentile / 100) * sorted.length) - 1;
    return sorted[Math.max(0, index)];
  }

  /**
   * Get current calibrated timeout
   */
  getCurrentTimeout(): number {
    return this.currentTimeout;
  }

  /**
   * Get timeout configuration for network quality
   */
  getTimeoutForQuality(quality: NetworkQuality): number {
    // Return calibrated timeout, but ensure it meets minimum requirements for quality
    const qualityMinimums = {
      [NetworkQuality.EXCELLENT]: 10000,
      [NetworkQuality.GOOD]: 15000,
      [NetworkQuality.FAIR]: 30000,
      [NetworkQuality.POOR]: 60000
    };

    const qualityMinimum = qualityMinimums[quality];
    return Math.max(this.currentTimeout, qualityMinimum);
  }

  /**
   * Get calibration data for diagnostics
   */
  getCalibrationData(): CalibrationData {
    const recentRequests = this.requestHistory.slice(-20);
    const latencies = recentRequests.map(r => r.duration);
    const successCount = recentRequests.filter(r => r.success).length;

    return {
      currentTimeout: this.currentTimeout,
      observedLatencies: latencies,
      averageLatency: this.calculateAverage(latencies),
      p95Latency: this.calculatePercentile(latencies, 95),
      successRate: recentRequests.length > 0 ? successCount / recentRequests.length : 1,
      lastCalibration: Date.now(),
      networkSSID: this.lastNetworkSSID
    };
  }

  /**
   * Reset calibration to defaults
   */
  reset(): void {
    this.currentTimeout = this.config.platformDefault;
    this.requestHistory = [];
    if (this.config.persistenceEnabled) {
      this.clearCalibration();
    }
  }

  /**
   * Force set timeout (for testing or manual override)
   */
  setTimeout(timeout: number): void {
    this.currentTimeout = Math.max(
      this.config.minTimeout,
      Math.min(this.config.maxTimeout, timeout)
    );
    if (this.config.persistenceEnabled) {
      this.saveCalibration();
    }
  }

  /**
   * Update network context (for network-specific calibration)
   */
  updateNetworkContext(ssid?: string): void {
    if (ssid && ssid !== this.lastNetworkSSID) {
      console.log(`Network changed from ${this.lastNetworkSSID} to ${ssid}, resetting calibration`);
      this.lastNetworkSSID = ssid;
      this.reset();
    }
  }

  /**
   * Load calibration from persistent storage
   */
  private loadCalibration(): void {
    if (!this.config.persistenceEnabled || typeof window === 'undefined') {
      return;
    }

    try {
      const stored = localStorage.getItem(this.storageKey);
      if (stored) {
        const data: CalibrationData = JSON.parse(stored);
        
        // Check if calibration is recent (within 24 hours)
        const age = Date.now() - data.lastCalibration;
        if (age < 24 * 60 * 60 * 1000) {
          this.currentTimeout = data.currentTimeout;
          this.lastNetworkSSID = data.networkSSID;
          console.log('Loaded calibrated timeout:', this.currentTimeout);
        }
      }
    } catch (error) {
      console.warn('Failed to load timeout calibration:', error);
    }
  }

  /**
   * Save calibration to persistent storage
   */
  private saveCalibration(): void {
    if (!this.config.persistenceEnabled || typeof window === 'undefined') {
      return;
    }

    try {
      const data = this.getCalibrationData();
      localStorage.setItem(this.storageKey, JSON.stringify(data));
    } catch (error) {
      console.warn('Failed to save timeout calibration:', error);
    }
  }

  /**
   * Clear calibration from storage
   */
  private clearCalibration(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(this.storageKey);
    }
  }

  /**
   * Get recommendation for retry configuration based on calibration
   */
  getRetryRecommendation(): {
    maxRetries: number;
    retryDelay: number;
    backoffMultiplier: number;
  } {
    const data = this.getCalibrationData();

    if (data.successRate > 0.95) {
      // Excellent success rate: minimal retries
      return {
        maxRetries: 3,
        retryDelay: 1000,
        backoffMultiplier: 2
      };
    } else if (data.successRate > 0.85) {
      // Good success rate: moderate retries
      return {
        maxRetries: 5,
        retryDelay: 2000,
        backoffMultiplier: 2
      };
    } else if (data.successRate > 0.70) {
      // Fair success rate: more retries
      return {
        maxRetries: 7,
        retryDelay: 3000,
        backoffMultiplier: 1.5
      };
    } else {
      // Poor success rate: maximum retries with conservative backoff
      return {
        maxRetries: 10,
        retryDelay: 5000,
        backoffMultiplier: 1.8
      };
    }
  }
}

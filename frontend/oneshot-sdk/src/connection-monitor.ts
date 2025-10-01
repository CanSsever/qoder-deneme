/**
 * Real-time Connection Health Monitoring System
 * Provides continuous monitoring of connection health and proactive issue detection
 */

import { NetworkQualityAssessment, NetworkQuality, ConnectionAssessment } from './network-quality';
import { circuitBreakerManager } from './circuit-breaker';

export interface ConnectionHealthStatus {
  isHealthy: boolean;
  currentQuality: NetworkQuality;
  lastAssessment: ConnectionAssessment;
  alertLevel: AlertLevel;
  issues: HealthIssue[];
  recommendations: string[];
  uptime: number;
  lastHealthyTime: number;
}

export enum AlertLevel {
  NONE = 'none',
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export interface HealthIssue {
  type: IssueType;
  severity: AlertLevel;
  message: string;
  detectedAt: number;
  persistenceDuration: number;
}

export enum IssueType {
  HIGH_LATENCY = 'high_latency',
  LOW_BANDWIDTH = 'low_bandwidth',
  UNSTABLE_CONNECTION = 'unstable_connection',
  HIGH_ERROR_RATE = 'high_error_rate',
  CIRCUIT_BREAKER_ISSUES = 'circuit_breaker_issues',
  AUTHENTICATION_FAILURES = 'authentication_failures'
}

export interface MonitoringConfig {
  checkInterval: number;
  healthThresholds: HealthThresholds;
  alertThresholds: AlertThresholds;
  historyRetention: number;
}

export interface HealthThresholds {
  minBandwidth: number;
  maxLatency: number;
  minStability: number;
  maxErrorRate: number;
}

export interface AlertThresholds {
  highLatency: number;
  lowBandwidth: number;
  unstableConnection: number;
  highErrorRate: number;
}

export class ConnectionHealthMonitor {
  private networkAssessment: NetworkQualityAssessment;
  private monitoringInterval?: NodeJS.Timeout;
  private healthHistory: ConnectionHealthStatus[] = [];
  private currentStatus?: ConnectionHealthStatus;
  private config: MonitoringConfig;
  private activeIssues: Map<IssueType, HealthIssue> = new Map();
  private listeners: Set<(status: ConnectionHealthStatus) => void> = new Set();
  private startTime: number = Date.now();

  constructor(baseUrl: string, config?: Partial<MonitoringConfig>) {
    this.networkAssessment = new NetworkQualityAssessment(baseUrl);
    this.config = {
      checkInterval: 30000, // 30 seconds
      healthThresholds: {
        minBandwidth: 128, // 128 Kbps
        maxLatency: 1000,  // 1 second
        minStability: 80,  // 80%
        maxErrorRate: 10   // 10%
      },
      alertThresholds: {
        highLatency: 2000,     // 2 seconds
        lowBandwidth: 64,      // 64 Kbps
        unstableConnection: 60, // 60%
        highErrorRate: 20      // 20%
      },
      historyRetention: 3600000, // 1 hour
      ...config
    };
  }

  /**
   * Start continuous health monitoring
   */
  startMonitoring(): void {
    if (this.monitoringInterval) {
      this.stopMonitoring();
    }

    console.log('Starting connection health monitoring...');
    
    // Perform initial assessment
    this.performHealthCheck();
    
    // Schedule regular checks
    this.monitoringInterval = setInterval(() => {
      this.performHealthCheck();
    }, this.config.checkInterval);
  }

  /**
   * Stop health monitoring
   */
  stopMonitoring(): void {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = undefined;
      console.log('Connection health monitoring stopped');
    }
  }

  /**
   * Get current health status
   */
  getCurrentStatus(): ConnectionHealthStatus | undefined {
    return this.currentStatus;
  }

  /**
   * Get health history
   */
  getHealthHistory(): ConnectionHealthStatus[] {
    return [...this.healthHistory];
  }

  /**
   * Add status change listener
   */
  addStatusListener(listener: (status: ConnectionHealthStatus) => void): void {
    this.listeners.add(listener);
  }

  /**
   * Remove status change listener
   */
  removeStatusListener(listener: (status: ConnectionHealthStatus) => void): void {
    this.listeners.delete(listener);
  }

  /**
   * Perform immediate health check
   */
  async performHealthCheck(): Promise<ConnectionHealthStatus> {
    try {
      const assessment = await this.networkAssessment.assessNetworkQuality();
      const circuitMetrics = circuitBreakerManager.getAllMetrics();
      
      const status = this.analyzeHealthStatus(assessment, circuitMetrics);
      
      this.updateCurrentStatus(status);
      this.addToHistory(status);
      this.notifyListeners(status);
      
      return status;
    } catch (error) {
      console.warn('Health check failed:', error);
      
      const fallbackStatus = this.createFallbackStatus();
      this.updateCurrentStatus(fallbackStatus);
      
      return fallbackStatus;
    }
  }

  /**
   * Analyze health status from assessment data
   */
  private analyzeHealthStatus(
    assessment: ConnectionAssessment,
    circuitMetrics: Record<string, any>
  ): ConnectionHealthStatus {
    const now = Date.now();
    const { metrics, quality } = assessment;
    const issues: HealthIssue[] = [];
    let alertLevel = AlertLevel.NONE;
    const recommendations: string[] = [];

    // Check latency issues
    if (metrics.latency > this.config.alertThresholds.highLatency) {
      const issue = this.createOrUpdateIssue(IssueType.HIGH_LATENCY, {
        severity: metrics.latency > 3000 ? AlertLevel.CRITICAL : AlertLevel.HIGH,
        message: `High latency detected: ${metrics.latency}ms`,
        detectedAt: now
      });
      issues.push(issue);
      recommendations.push('Consider switching to a faster network connection');
    }

    // Check bandwidth issues
    if (metrics.bandwidth < this.config.alertThresholds.lowBandwidth) {
      const issue = this.createOrUpdateIssue(IssueType.LOW_BANDWIDTH, {
        severity: metrics.bandwidth < 32 ? AlertLevel.CRITICAL : AlertLevel.HIGH,
        message: `Low bandwidth detected: ${metrics.bandwidth} Kbps`,
        detectedAt: now
      });
      issues.push(issue);
      recommendations.push('Switch to WiFi or better cellular connection');
    }

    // Check stability issues
    if (metrics.stability < this.config.alertThresholds.unstableConnection) {
      const issue = this.createOrUpdateIssue(IssueType.UNSTABLE_CONNECTION, {
        severity: metrics.stability < 50 ? AlertLevel.CRITICAL : AlertLevel.MEDIUM,
        message: `Unstable connection: ${metrics.stability}% stability`,
        detectedAt: now
      });
      issues.push(issue);
      recommendations.push('Move to area with better signal or switch networks');
    }

    // Check error rate issues
    if (metrics.errorRate > this.config.alertThresholds.highErrorRate) {
      const issue = this.createOrUpdateIssue(IssueType.HIGH_ERROR_RATE, {
        severity: metrics.errorRate > 30 ? AlertLevel.CRITICAL : AlertLevel.HIGH,
        message: `High error rate: ${metrics.errorRate}%`,
        detectedAt: now
      });
      issues.push(issue);
      recommendations.push('Check network configuration or contact support');
    }

    // Check circuit breaker issues
    const unhealthyBreakers = Object.entries(circuitMetrics)
      .filter(([_, metrics]) => metrics.state !== 'closed')
      .map(([name]) => name);

    if (unhealthyBreakers.length > 0) {
      const issue = this.createOrUpdateIssue(IssueType.CIRCUIT_BREAKER_ISSUES, {
        severity: AlertLevel.HIGH,
        message: `Circuit breakers open: ${unhealthyBreakers.join(', ')}`,
        detectedAt: now
      });
      issues.push(issue);
      recommendations.push('Service temporarily unavailable, please wait');
    }

    // Determine overall alert level
    alertLevel = this.calculateOverallAlertLevel(issues);

    // Calculate uptime
    const uptime = this.calculateUptime();
    const lastHealthyTime = this.getLastHealthyTime();

    // Determine if connection is healthy
    const isHealthy = this.isConnectionHealthy(metrics, alertLevel);

    // Clean up resolved issues
    this.cleanupResolvedIssues(issues);

    return {
      isHealthy,
      currentQuality: quality,
      lastAssessment: assessment,
      alertLevel,
      issues,
      recommendations,
      uptime,
      lastHealthyTime
    };
  }

  /**
   * Create or update an issue
   */
  private createOrUpdateIssue(type: IssueType, newIssue: Partial<HealthIssue>): HealthIssue {
    const existing = this.activeIssues.get(type);
    const now = Date.now();

    if (existing) {
      // Update existing issue
      const updated = {
        ...existing,
        ...newIssue,
        persistenceDuration: now - existing.detectedAt
      };
      this.activeIssues.set(type, updated);
      return updated;
    } else {
      // Create new issue
      const issue: HealthIssue = {
        type,
        severity: newIssue.severity || AlertLevel.MEDIUM,
        message: newIssue.message || 'Connection issue detected',
        detectedAt: newIssue.detectedAt || now,
        persistenceDuration: 0
      };
      this.activeIssues.set(type, issue);
      return issue;
    }
  }

  /**
   * Calculate overall alert level from issues
   */
  private calculateOverallAlertLevel(issues: HealthIssue[]): AlertLevel {
    if (issues.length === 0) return AlertLevel.NONE;

    const severityLevels = {
      [AlertLevel.NONE]: 0,
      [AlertLevel.LOW]: 1,
      [AlertLevel.MEDIUM]: 2,
      [AlertLevel.HIGH]: 3,
      [AlertLevel.CRITICAL]: 4
    };

    const maxSeverity = Math.max(
      ...issues.map(issue => severityLevels[issue.severity])
    );

    return Object.keys(severityLevels)[maxSeverity] as AlertLevel;
  }

  /**
   * Check if connection is healthy based on thresholds
   */
  private isConnectionHealthy(metrics: any, alertLevel: AlertLevel): boolean {
    const { minBandwidth, maxLatency, minStability, maxErrorRate } = this.config.healthThresholds;
    
    return (
      metrics.bandwidth >= minBandwidth &&
      metrics.latency <= maxLatency &&
      metrics.stability >= minStability &&
      metrics.errorRate <= maxErrorRate &&
      alertLevel <= AlertLevel.MEDIUM
    );
  }

  /**
   * Calculate uptime percentage
   */
  private calculateUptime(): number {
    if (this.healthHistory.length === 0) return 100;

    const healthyCount = this.healthHistory.filter(status => status.isHealthy).length;
    return (healthyCount / this.healthHistory.length) * 100;
  }

  /**
   * Get timestamp of last healthy status
   */
  private getLastHealthyTime(): number {
    const lastHealthy = [...this.healthHistory]
      .reverse()
      .find(status => status.isHealthy);
    
    return lastHealthy?.lastAssessment.metrics.timestamp || this.startTime;
  }

  /**
   * Clean up resolved issues
   */
  private cleanupResolvedIssues(currentIssues: HealthIssue[]): void {
    const currentIssueTypes = new Set(currentIssues.map(issue => issue.type));
    
    for (const [type] of this.activeIssues) {
      if (!currentIssueTypes.has(type)) {
        this.activeIssues.delete(type);
      }
    }
  }

  /**
   * Update current status
   */
  private updateCurrentStatus(status: ConnectionHealthStatus): void {
    this.currentStatus = status;
  }

  /**
   * Add status to history
   */
  private addToHistory(status: ConnectionHealthStatus): void {
    this.healthHistory.push(status);
    
    // Clean up old history
    const cutoffTime = Date.now() - this.config.historyRetention;
    this.healthHistory = this.healthHistory.filter(
      s => s.lastAssessment.metrics.timestamp > cutoffTime
    );
  }

  /**
   * Notify all listeners of status change
   */
  private notifyListeners(status: ConnectionHealthStatus): void {
    for (const listener of this.listeners) {
      try {
        listener(status);
      } catch (error) {
        console.warn('Error notifying health status listener:', error);
      }
    }
  }

  /**
   * Create fallback status for error conditions
   */
  private createFallbackStatus(): ConnectionHealthStatus {
    return {
      isHealthy: false,
      currentQuality: NetworkQuality.POOR,
      lastAssessment: {
        quality: NetworkQuality.POOR,
        metrics: {
          latency: 5000,
          bandwidth: 32,
          stability: 30,
          errorRate: 50,
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
      },
      alertLevel: AlertLevel.CRITICAL,
      issues: [{
        type: IssueType.HIGH_ERROR_RATE,
        severity: AlertLevel.CRITICAL,
        message: 'Health monitoring failed',
        detectedAt: Date.now(),
        persistenceDuration: 0
      }],
      recommendations: ['Check network connection', 'Contact support if issue persists'],
      uptime: 0,
      lastHealthyTime: this.startTime
    };
  }

  /**
   * Get health summary for reporting
   */
  getHealthSummary(): {
    status: string;
    quality: NetworkQuality;
    uptime: number;
    activeIssues: number;
    recommendations: string[];
  } {
    const current = this.getCurrentStatus();
    
    if (!current) {
      return {
        status: 'unknown',
        quality: NetworkQuality.POOR,
        uptime: 0,
        activeIssues: 0,
        recommendations: ['Start monitoring to get health status']
      };
    }

    return {
      status: current.isHealthy ? 'healthy' : 'unhealthy',
      quality: current.currentQuality,
      uptime: current.uptime,
      activeIssues: current.issues.length,
      recommendations: current.recommendations
    };
  }
}
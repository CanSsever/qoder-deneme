/**
 * Circuit Breaker Pattern Implementation
 * Implements fail-fast mechanism to prevent cascade failures during authentication
 */

export enum CircuitState {
  CLOSED = 'closed',
  OPEN = 'open', 
  HALF_OPEN = 'half_open'
}

export interface CircuitBreakerConfig {
  failureThreshold: number;
  recoveryTimeout: number;
  successThreshold: number;
  monitoringWindow: number;
}

export interface CircuitBreakerMetrics {
  state: CircuitState;
  failureCount: number;
  successCount: number;
  lastFailureTime: number;
  lastSuccessTime: number;
  totalRequests: number;
  totalFailures: number;
  uptime: number;
}

export interface RequestResult {
  success: boolean;
  duration: number;
  error?: string;
  timestamp: number;
}

export class CircuitBreaker {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount: number = 0;
  private successCount: number = 0;
  private lastFailureTime: number = 0;
  private lastSuccessTime: number = 0;
  private nextAttemptTime: number = 0;
  private totalRequests: number = 0;
  private totalFailures: number = 0;
  private requestHistory: RequestResult[] = [];
  private readonly config: CircuitBreakerConfig;
  private readonly name: string;

  constructor(name: string, config?: Partial<CircuitBreakerConfig>) {
    this.name = name;
    this.config = {
      failureThreshold: 5,           // Open circuit after 5 failures
      recoveryTimeout: 30000,        // Wait 30s before trying again
      successThreshold: 3,           // Close circuit after 3 successes in half-open
      monitoringWindow: 60000,       // Monitor last 60s of requests
      ...config
    };
  }

  /**
   * Execute a request through the circuit breaker
   */
  async execute<T>(requestFn: () => Promise<T>): Promise<T> {
    // Check if circuit allows request
    if (!this.canExecuteRequest()) {
      throw new CircuitBreakerError(
        `Circuit breaker is ${this.state}. Next attempt allowed at ${new Date(this.nextAttemptTime).toISOString()}`,
        this.state,
        this.getMetrics()
      );
    }

    const startTime = Date.now();
    this.totalRequests++;

    try {
      const result = await requestFn();
      const duration = Date.now() - startTime;
      
      this.onSuccess(duration);
      return result;
    } catch (error: any) {
      const duration = Date.now() - startTime;
      
      this.onFailure(duration, error.message);
      throw error;
    }
  }

  /**
   * Check if the circuit breaker allows request execution
   */
  private canExecuteRequest(): boolean {
    const now = Date.now();

    switch (this.state) {
      case CircuitState.CLOSED:
        return true;

      case CircuitState.OPEN:
        if (now >= this.nextAttemptTime) {
          this.state = CircuitState.HALF_OPEN;
          this.successCount = 0;
          console.log(`Circuit breaker ${this.name}: Transitioning to HALF_OPEN`);
          return true;
        }
        return false;

      case CircuitState.HALF_OPEN:
        return true;

      default:
        return false;
    }
  }

  /**
   * Handle successful request
   */
  private onSuccess(duration: number): void {
    const now = Date.now();
    this.lastSuccessTime = now;
    this.successCount++;
    
    this.addToHistory({
      success: true,
      duration,
      timestamp: now
    });

    switch (this.state) {
      case CircuitState.HALF_OPEN:
        if (this.successCount >= this.config.successThreshold) {
          this.reset();
          console.log(`Circuit breaker ${this.name}: Closing circuit after ${this.successCount} successes`);
        }
        break;

      case CircuitState.CLOSED:
        // Reset failure count on success
        this.failureCount = 0;
        break;
    }
  }

  /**
   * Handle failed request
   */
  private onFailure(duration: number, error: string): void {
    const now = Date.now();
    this.lastFailureTime = now;
    this.failureCount++;
    this.totalFailures++;

    this.addToHistory({
      success: false,
      duration,
      error,
      timestamp: now
    });

    switch (this.state) {
      case CircuitState.CLOSED:
        if (this.failureCount >= this.config.failureThreshold) {
          this.openCircuit();
        }
        break;

      case CircuitState.HALF_OPEN:
        this.openCircuit();
        break;
    }
  }

  /**
   * Open the circuit breaker
   */
  private openCircuit(): void {
    this.state = CircuitState.OPEN;
    this.nextAttemptTime = Date.now() + this.config.recoveryTimeout;
    console.log(`Circuit breaker ${this.name}: Opening circuit due to ${this.failureCount} failures. Next attempt at ${new Date(this.nextAttemptTime).toISOString()}`);
  }

  /**
   * Reset circuit breaker to closed state
   */
  private reset(): void {
    this.state = CircuitState.CLOSED;
    this.failureCount = 0;
    this.successCount = 0;
    this.nextAttemptTime = 0;
  }

  /**
   * Add request result to history for monitoring
   */
  private addToHistory(result: RequestResult): void {
    this.requestHistory.push(result);
    
    // Keep only recent history within monitoring window
    const cutoffTime = Date.now() - this.config.monitoringWindow;
    this.requestHistory = this.requestHistory.filter(
      record => record.timestamp > cutoffTime
    );
  }

  /**
   * Get current circuit breaker metrics
   */
  getMetrics(): CircuitBreakerMetrics {
    const now = Date.now();
    const recentRequests = this.requestHistory.filter(
      record => record.timestamp > now - this.config.monitoringWindow
    );

    return {
      state: this.state,
      failureCount: this.failureCount,
      successCount: this.successCount,
      lastFailureTime: this.lastFailureTime,
      lastSuccessTime: this.lastSuccessTime,
      totalRequests: this.totalRequests,
      totalFailures: this.totalFailures,
      uptime: this.calculateUptime()
    };
  }

  /**
   * Calculate uptime percentage
   */
  private calculateUptime(): number {
    if (this.totalRequests === 0) return 100;
    
    const successRate = ((this.totalRequests - this.totalFailures) / this.totalRequests) * 100;
    return Math.max(0, Math.min(100, successRate));
  }

  /**
   * Get human-readable state description
   */
  getStateDescription(): string {
    switch (this.state) {
      case CircuitState.CLOSED:
        return 'Closed - All requests allowed';
      case CircuitState.OPEN:
        const waitTime = Math.max(0, this.nextAttemptTime - Date.now());
        return `Open - Requests blocked for ${Math.ceil(waitTime / 1000)}s`;
      case CircuitState.HALF_OPEN:
        return `Half-Open - Testing with limited requests (${this.successCount}/${this.config.successThreshold} successes)`;
      default:
        return 'Unknown state';
    }
  }

  /**
   * Force reset the circuit breaker (for testing/admin purposes)
   */
  forceReset(): void {
    this.reset();
    this.requestHistory = [];
    this.totalRequests = 0;
    this.totalFailures = 0;
    console.log(`Circuit breaker ${this.name}: Force reset completed`);
  }

  /**
   * Force open the circuit breaker (for maintenance mode)
   */
  forceOpen(duration?: number): void {
    this.state = CircuitState.OPEN;
    this.nextAttemptTime = Date.now() + (duration || this.config.recoveryTimeout);
    console.log(`Circuit breaker ${this.name}: Force opened until ${new Date(this.nextAttemptTime).toISOString()}`);
  }

  /**
   * Check if circuit breaker is healthy
   */
  isHealthy(): boolean {
    const metrics = this.getMetrics();
    return metrics.state === CircuitState.CLOSED && metrics.uptime > 90;
  }

  /**
   * Get recent error rate
   */
  getRecentErrorRate(): number {
    const now = Date.now();
    const recentRequests = this.requestHistory.filter(
      record => record.timestamp > now - this.config.monitoringWindow
    );

    if (recentRequests.length === 0) return 0;

    const failures = recentRequests.filter(record => !record.success).length;
    return (failures / recentRequests.length) * 100;
  }

  /**
   * Get average response time for successful requests
   */
  getAverageResponseTime(): number {
    const successfulRequests = this.requestHistory.filter(record => record.success);
    if (successfulRequests.length === 0) return 0;

    const totalDuration = successfulRequests.reduce((sum, record) => sum + record.duration, 0);
    return totalDuration / successfulRequests.length;
  }
}

/**
 * Circuit Breaker Error class
 */
export class CircuitBreakerError extends Error {
  public readonly circuitState: CircuitState;
  public readonly metrics: CircuitBreakerMetrics;

  constructor(message: string, state: CircuitState, metrics: CircuitBreakerMetrics) {
    super(message);
    this.name = 'CircuitBreakerError';
    this.circuitState = state;
    this.metrics = metrics;
  }
}

/**
 * Circuit Breaker Manager for handling multiple circuit breakers
 */
export class CircuitBreakerManager {
  private breakers: Map<string, CircuitBreaker> = new Map();

  /**
   * Get or create a circuit breaker
   */
  getBreaker(name: string, config?: Partial<CircuitBreakerConfig>): CircuitBreaker {
    if (!this.breakers.has(name)) {
      this.breakers.set(name, new CircuitBreaker(name, config));
    }
    return this.breakers.get(name)!;
  }

  /**
   * Get all circuit breaker metrics
   */
  getAllMetrics(): Record<string, CircuitBreakerMetrics> {
    const metrics: Record<string, CircuitBreakerMetrics> = {};
    
    for (const [name, breaker] of this.breakers.entries()) {
      metrics[name] = breaker.getMetrics();
    }

    return metrics;
  }

  /**
   * Reset all circuit breakers
   */
  resetAll(): void {
    for (const breaker of this.breakers.values()) {
      breaker.forceReset();
    }
  }

  /**
   * Get health status of all circuit breakers
   */
  getHealthStatus(): { healthy: string[]; unhealthy: string[] } {
    const healthy: string[] = [];
    const unhealthy: string[] = [];

    for (const [name, breaker] of this.breakers.entries()) {
      if (breaker.isHealthy()) {
        healthy.push(name);
      } else {
        unhealthy.push(name);
      }
    }

    return { healthy, unhealthy };
  }
}

// Global circuit breaker manager instance
export const circuitBreakerManager = new CircuitBreakerManager();
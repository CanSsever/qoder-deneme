/**
 * Comprehensive test suite for enhanced authentication with network resilience
 */

import { OneShotClient } from '../src/client';
import { NetworkQualityAssessment, NetworkQuality } from '../src/network-quality';
import { CircuitBreaker, CircuitState } from '../src/circuit-breaker';
import { ErrorClassifier, ErrorType } from '../src/error-classification';
import { DemoModeManager } from '../src/demo-mode';
import { ConnectionHealthMonitor } from '../src/connection-monitor';

// Mock server setup for testing different network conditions
const mockServer = {
  baseUrl: 'http://localhost:3001',
  responses: new Map<string, any>(),
  delays: new Map<string, number>(),
  failureRates: new Map<string, number>(),

  setResponse(endpoint: string, response: any, delay = 0, failureRate = 0) {
    this.responses.set(endpoint, response);
    this.delays.set(endpoint, delay);
    this.failureRates.set(endpoint, failureRate);
  },

  reset() {
    this.responses.clear();
    this.delays.clear();
    this.failureRates.clear();
  }
};

describe('Enhanced Authentication System', () => {
  let client: OneShotClient;
  let networkAssessment: NetworkQualityAssessment;
  let circuitBreaker: CircuitBreaker;
  let demoMode: DemoModeManager;
  let healthMonitor: ConnectionHealthMonitor;

  beforeEach(() => {
    mockServer.reset();
    
    client = new OneShotClient({
      baseUrl: mockServer.baseUrl,
      timeout: 30000,
      retryAttempts: 5,
      retryDelay: 1000
    });

    networkAssessment = new NetworkQualityAssessment(mockServer.baseUrl);
    circuitBreaker = new CircuitBreaker('test-auth', {
      failureThreshold: 3,
      recoveryTimeout: 5000,
      successThreshold: 2
    });
    demoMode = new DemoModeManager();
    healthMonitor = new ConnectionHealthMonitor(mockServer.baseUrl);
  });

  afterEach(() => {
    healthMonitor.stopMonitoring();
  });

  describe('Network Quality Assessment', () => {
    test('should classify excellent network conditions', async () => {
      mockServer.setResponse('/healthz', { status: 'ok' }, 50); // 50ms latency

      const assessment = await networkAssessment.assessNetworkQuality();

      expect(assessment.quality).toBe(NetworkQuality.EXCELLENT);
      expect(assessment.metrics.latency).toBeLessThan(100);
      expect(assessment.recommendedTimeout).toBe(15000);
      expect(assessment.maxRetries).toBe(3);
    });

    test('should classify poor network conditions', async () => {
      mockServer.setResponse('/healthz', { status: 'ok' }, 2000); // 2s latency

      const assessment = await networkAssessment.assessNetworkQuality();

      expect(assessment.quality).toBe(NetworkQuality.POOR);
      expect(assessment.metrics.latency).toBeGreaterThan(1000);
      expect(assessment.recommendedTimeout).toBe(60000);
      expect(assessment.maxRetries).toBe(10);
    });

    test('should adapt timeout based on network quality', async () => {
      // Test excellent conditions
      mockServer.setResponse('/healthz', { status: 'ok' }, 80);
      let assessment = await networkAssessment.assessNetworkQuality();
      expect(assessment.recommendedTimeout).toBe(15000);

      // Test poor conditions
      mockServer.setResponse('/healthz', { status: 'ok' }, 1500);
      assessment = await networkAssessment.assessNetworkQuality();
      expect(assessment.recommendedTimeout).toBeGreaterThan(45000);
    });
  });

  describe('Circuit Breaker Pattern', () => {
    test('should open circuit after failure threshold', async () => {
      // Simulate failures
      for (let i = 0; i < 5; i++) {
        try {
          await circuitBreaker.execute(async () => {
            throw new Error('Service failure');
          });
        } catch (error) {
          // Expected failures
        }
      }

      expect(circuitBreaker.getMetrics().state).toBe(CircuitState.OPEN);
    });

    test('should transition to half-open after recovery timeout', async () => {
      // Force circuit open
      circuitBreaker.forceOpen(1000); // 1 second

      expect(circuitBreaker.getMetrics().state).toBe(CircuitState.OPEN);

      // Wait for recovery timeout
      await new Promise(resolve => setTimeout(resolve, 1100));

      // Next request should be allowed (half-open)
      try {
        await circuitBreaker.execute(async () => ({ success: true }));
      } catch {
        // Ignore for state check
      }

      expect(circuitBreaker.getMetrics().state).toBe(CircuitState.HALF_OPEN);
    });

    test('should close circuit after successful requests in half-open', async () => {
      circuitBreaker.forceOpen(100);
      await new Promise(resolve => setTimeout(resolve, 150));

      // Succeed enough times to close circuit
      for (let i = 0; i < 3; i++) {
        await circuitBreaker.execute(async () => ({ success: true }));
      }

      expect(circuitBreaker.getMetrics().state).toBe(CircuitState.CLOSED);
    });
  });

  describe('Adaptive Authentication', () => {
    test('should succeed with good network conditions', async () => {
      mockServer.setResponse('/healthz', { status: 'ok' }, 100);
      mockServer.setResponse('/api/v1/auth/login', {
        access_token: 'test_token',
        user: {
          id: 'user_123',
          email: 'test@example.com',
          credits: 10
        }
      }, 200);

      const response = await client.login('test@example.com', 'password123');

      expect(response.access_token).toBe('test_token');
      expect(response.user.email).toBe('test@example.com');
    });

    test('should retry on timeout with exponential backoff', async () => {
      let attemptCount = 0;
      const startTime = Date.now();

      mockServer.setResponse('/healthz', { status: 'ok' }, 100);
      
      // Mock login that fails first 2 attempts, succeeds on 3rd
      mockServer.setResponse('/api/v1/auth/login', () => {
        attemptCount++;
        if (attemptCount < 3) {
          throw new Error('Request timeout');
        }
        return {
          access_token: 'success_token',
          user: { id: 'user_123', email: 'test@example.com', credits: 10 }
        };
      });

      const response = await client.login('test@example.com', 'password123');
      const totalTime = Date.now() - startTime;

      expect(response.access_token).toBe('success_token');
      expect(attemptCount).toBe(3);
      expect(totalTime).toBeGreaterThan(2000); // Should have backoff delays
    });

    test('should provide progressive feedback during retries', async () => {
      const progressMessages: string[] = [];

      mockServer.setResponse('/healthz', { status: 'ok' }, 100);
      mockServer.setResponse('/api/v1/auth/login', () => {
        throw new Error('Service unavailable');
      });

      try {
        await client.login('test@example.com', 'password123', {
          onProgress: (message) => progressMessages.push(message),
          maxAttempts: 3
        });
      } catch (error) {
        // Expected to fail
      }

      expect(progressMessages.length).toBeGreaterThan(2);
      expect(progressMessages[0]).toContain('Checking server connectivity');
      expect(progressMessages.some(msg => msg.includes('Connecting to server'))).toBe(true);
      expect(progressMessages.some(msg => msg.includes('retrying'))).toBe(true);
    });
  });

  describe('Error Classification', () => {
    test('should classify timeout errors correctly', () => {
      const timeoutError = new Error('Request timeout');
      timeoutError.name = 'AbortError';

      const classification = ErrorClassifier.classifyError(
        timeoutError,
        NetworkQuality.POOR,
        CircuitState.CLOSED,
        2
      );

      expect(classification.type).toBe(ErrorType.CONNECTION_TIMEOUT);
      expect(classification.retryRecommended).toBe(true);
      expect(classification.userMessage).toContain('timeout');
      expect(classification.recoveryOptions.length).toBeGreaterThan(0);
    });

    test('should classify server errors correctly', () => {
      const serverError = { status: 503, message: 'Service unavailable' };

      const classification = ErrorClassifier.classifyError(serverError);

      expect(classification.type).toBe(ErrorType.SERVER_UNAVAILABLE);
      expect(classification.retryRecommended).toBe(true);
      expect(classification.userMessage).toContain('temporarily unavailable');
    });

    test('should classify authentication errors correctly', () => {
      const authError = { status: 401, message: 'Invalid credentials' };

      const classification = ErrorClassifier.classifyError(authError);

      expect(classification.type).toBe(ErrorType.AUTHENTICATION_FAILED);
      expect(classification.retryRecommended).toBe(false);
      expect(classification.userMessage).toContain('credentials');
    });

    test('should classify network errors with diagnostic suggestions', () => {
      const networkError = new Error('fetch failed');

      const classification = ErrorClassifier.classifyError(
        networkError,
        NetworkQuality.POOR
      );

      expect(classification.type).toBe(ErrorType.NETWORK_UNREACHABLE);
      expect(classification.networkDiagnostics).toBeDefined();
      expect(classification.networkDiagnostics!.length).toBeGreaterThan(0);
      expect(classification.recommendations.length).toBeGreaterThan(0);
    });
  });

  describe('Demo Mode Functionality', () => {
    beforeEach(() => {
      demoMode.enableDemoMode();
    });

    test('should authenticate with demo credentials', async () => {
      const response = await demoMode.mockLogin('demo@example.com', 'demo123');

      expect(response.access_token).toContain('demo_token');
      expect(response.user.email).toBe('demo@example.com');
      expect(response.user.credits).toBe(5);
      expect(response.user.subscription_status).toBe('demo');
    });

    test('should reject invalid demo credentials', async () => {
      await expect(
        demoMode.mockLogin('invalid@example.com', 'wrong')
      ).rejects.toThrow('Invalid demo credentials');
    });

    test('should create mock jobs with limitations', async () => {
      await demoMode.mockLogin('demo@example.com', 'demo123');

      const job1 = await demoMode.mockCreateJob('face_swap', 'input1.jpg', 'target1.jpg');
      const job2 = await demoMode.mockCreateJob('upscale', 'input2.jpg');
      const job3 = await demoMode.mockCreateJob('face_restore', 'input3.jpg');

      expect(job1.job_id).toContain('demo-job');
      expect(job2.status).toBe('queued');
      expect(job1.credits_cost).toBe(1);

      // Should fail on 4th job due to demo limits
      await expect(
        demoMode.mockCreateJob('face_swap', 'input4.jpg')
      ).rejects.toThrow('Demo mode limited to 3 jobs');
    });

    test('should complete mock jobs over time', async () => {
      await demoMode.mockLogin('demo@example.com', 'demo123');
      
      const job = await demoMode.mockCreateJob('face_swap', 'input.jpg', 'target.jpg');
      expect(job.status).toBe('queued');
      expect(job.estimated_time).toBeGreaterThan(0);

      // Wait for mock completion
      await new Promise(resolve => setTimeout(resolve, 5500));

      const updatedJob = await demoMode.mockGetJob(job.job_id);
      expect(updatedJob.status).toBe('succeeded');
      expect(updatedJob.result_url).toContain('.jpg');
      expect(updatedJob.progress).toBe(100);
    });

    test('should provide demo limitations info', () => {
      const limitations = demoMode.getLimitations();

      expect(limitations.length).toBeGreaterThan(0);
      expect(limitations.some(l => l.feature === 'Job Processing')).toBe(true);
      expect(limitations.some(l => l.restriction.includes('Limited to 3'))).toBe(true);
    });
  });

  describe('Connection Health Monitoring', () => {
    test('should detect healthy connection', async () => {
      mockServer.setResponse('/healthz', { status: 'ok' }, 100);

      await healthMonitor.performHealthCheck();
      const status = healthMonitor.getCurrentStatus();

      expect(status?.isHealthy).toBe(true);
      expect(status?.currentQuality).toBe(NetworkQuality.EXCELLENT);
      expect(status?.issues.length).toBe(0);
    });

    test('should detect high latency issues', async () => {
      mockServer.setResponse('/healthz', { status: 'ok' }, 3000); // 3s latency

      await healthMonitor.performHealthCheck();
      const status = healthMonitor.getCurrentStatus();

      expect(status?.isHealthy).toBe(false);
      expect(status?.issues.some(issue => issue.type === 'high_latency')).toBe(true);
      expect(status?.recommendations.length).toBeGreaterThan(0);
    });

    test('should track health over time', async () => {
      // Good health initially
      mockServer.setResponse('/healthz', { status: 'ok' }, 100);
      await healthMonitor.performHealthCheck();

      // Poor health later
      mockServer.setResponse('/healthz', { status: 'ok' }, 2000);
      await healthMonitor.performHealthCheck();

      const history = healthMonitor.getHealthHistory();
      expect(history.length).toBe(2);
      expect(history[0].isHealthy).toBe(true);
      expect(history[1].isHealthy).toBe(false);
    });

    test('should notify listeners of status changes', async () => {
      const statusUpdates: any[] = [];
      
      healthMonitor.addStatusListener((status) => {
        statusUpdates.push(status);
      });

      mockServer.setResponse('/healthz', { status: 'ok' }, 100);
      await healthMonitor.performHealthCheck();

      expect(statusUpdates.length).toBe(1);
      expect(statusUpdates[0].isHealthy).toBe(true);
    });
  });

  describe('Integration Tests', () => {
    test('should handle complete authentication flow with network issues', async () => {
      const progressMessages: string[] = [];
      let networkQuality: NetworkQuality = NetworkQuality.POOR;

      // Start with poor network
      mockServer.setResponse('/healthz', { status: 'ok' }, 2000);
      
      // Authentication fails first few times, then succeeds
      let authAttempts = 0;
      mockServer.setResponse('/api/v1/auth/login', () => {
        authAttempts++;
        if (authAttempts < 3) {
          if (authAttempts === 1) {
            throw new Error('Request timeout');
          } else {
            throw { status: 503, message: 'Service unavailable' };
          }
        }
        
        // Network improves
        networkQuality = NetworkQuality.GOOD;
        return {
          access_token: 'recovery_token',
          user: {
            id: 'recovered_user',
            email: 'test@example.com',
            credits: 15
          }
        };
      });

      const response = await client.login('test@example.com', 'password123', {
        onProgress: (message) => progressMessages.push(message),
        maxAttempts: 5
      });

      expect(response.access_token).toBe('recovery_token');
      expect(authAttempts).toBe(3);
      expect(progressMessages.length).toBeGreaterThan(3);
      expect(progressMessages.some(msg => msg.includes('Poor connection detected'))).toBe(true);
    });

    test('should fall back to demo mode when authentication fails repeatedly', async () => {
      // Simulate complete authentication failure
      mockServer.setResponse('/healthz', () => { throw new Error('Network unreachable'); });

      demoMode.enableDemoMode();

      try {
        await client.login('test@example.com', 'password123', { maxAttempts: 2 });
      } catch (error) {
        // Expected failure
      }

      // Should be able to use demo mode as fallback
      const demoResponse = await demoMode.mockLogin('demo@example.com', 'demo123');
      expect(demoResponse.access_token).toContain('demo_token');

      const capabilities = demoMode.getCapabilities();
      expect(capabilities.canAuthenticate).toBe(true);
      expect(capabilities.canCreateJobs).toBe(true);
    });

    test('should provide comprehensive diagnostics when authentication fails', async () => {
      mockServer.setResponse('/healthz', () => { throw new Error('DNS resolution failed'); });

      try {
        await client.login('test@example.com', 'password123');
      } catch (error: any) {
        expect(error.name).toBe('ClassifiedError');
        expect(error.classification.type).toBe(ErrorType.NETWORK_UNREACHABLE);
        expect(error.classification.networkDiagnostics.length).toBeGreaterThan(0);
        expect(error.classification.recoveryOptions.length).toBeGreaterThan(0);
      }

      const diagnostics = await client.getNetworkDiagnostics();
      expect(diagnostics.networkQuality).toBeDefined();
      expect(diagnostics.circuitBreaker).toBeDefined();
    });
  });

  describe('Performance and Reliability', () => {
    test('should complete authentication within acceptable time limits', async () => {
      mockServer.setResponse('/healthz', { status: 'ok' }, 100);
      mockServer.setResponse('/api/v1/auth/login', {
        access_token: 'fast_token',
        user: { id: 'user_123', email: 'test@example.com', credits: 10 }
      }, 200);

      const startTime = Date.now();
      await client.login('test@example.com', 'password123');
      const duration = Date.now() - startTime;

      expect(duration).toBeLessThan(5000); // Should complete within 5 seconds
    });

    test('should handle concurrent authentication requests', async () => {
      mockServer.setResponse('/healthz', { status: 'ok' }, 100);
      mockServer.setResponse('/api/v1/auth/login', {
        access_token: 'concurrent_token',
        user: { id: 'user_123', email: 'test@example.com', credits: 10 }
      }, 300);

      const promises = Array(5).fill(0).map(() => 
        client.login('test@example.com', 'password123')
      );

      const results = await Promise.all(promises);
      
      expect(results.length).toBe(5);
      results.forEach(result => {
        expect(result.access_token).toBe('concurrent_token');
      });
    });

    test('should maintain circuit breaker state across requests', async () => {
      const client1 = new OneShotClient({ baseUrl: mockServer.baseUrl });
      const client2 = new OneShotClient({ baseUrl: mockServer.baseUrl });

      mockServer.setResponse('/healthz', { status: 'ok' }, 100);
      mockServer.setResponse('/api/v1/auth/login', () => {
        throw new Error('Service failure');
      });

      // Fail with client1 to open circuit
      for (let i = 0; i < 5; i++) {
        try {
          await client1.login('test@example.com', 'password123');
        } catch (error) {
          // Expected failures
        }
      }

      // client2 should also see the open circuit
      try {
        await client2.login('test@example.com', 'password123');
      } catch (error: any) {
        expect(error.message).toContain('Circuit breaker is open');
      }
    });
  });
});
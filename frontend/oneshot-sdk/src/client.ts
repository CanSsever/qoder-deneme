/**
 * OneShot SDK - Enhanced client with adaptive timeout and resilient authentication
 */
import { FetchHttpClient } from './http-client';
import { ErrorClassifier, UserFeedbackGenerator, ClassifiedError } from './error-classification';
import { NetworkQuality } from './network-quality';
import { PreflightValidator, ConnectionStatus, PreflightResult } from './preflight-validator';
import { ServiceDiscovery, DiscoveryResult, PlatformInfo } from './service-discovery';
import { AdaptiveTimeoutCalibrator } from './adaptive-timeout';
import {
  SdkConfig,
  LoginRequest,
  RegisterRequest,
  UserResponse,
  PresignRequest,
  PresignResponse,
  JobCreateRequest,
  JobResponse,
  JobStatusResponse,
  JobRead,
  Artifact,
  JobType,
  RequestOptions
} from './types';

export class OneShotClient {
  private httpClient: FetchHttpClient;
  private isAuthenticated = false;
  private authAttempts = 0;
  private lastAuthError?: ClassifiedError;
  private preflightValidator: PreflightValidator;
  private serviceDiscovery?: ServiceDiscovery;
  private timeoutCalibrator: AdaptiveTimeoutCalibrator;
  private baseUrl: string;

  constructor(config: SdkConfig) {
    this.baseUrl = config.baseUrl;
    
    // Initialize adaptive timeout calibrator
    this.timeoutCalibrator = new AdaptiveTimeoutCalibrator({
      platformDefault: config.timeout || 30000,
      persistenceEnabled: true
    });
    
    // Initialize HTTP client with calibrated timeout
    this.httpClient = new FetchHttpClient(
      config.baseUrl,
      this.timeoutCalibrator.getCurrentTimeout(),
      config.retryAttempts,
      config.retryDelay
    );
    
    // Initialize pre-flight validator
    this.preflightValidator = new PreflightValidator(config.baseUrl);

    // Set API key if provided
    if (config.apiKey) {
      this.httpClient.setBearerToken(config.apiKey);
      this.isAuthenticated = true;
    }
  }

  /**
   * Check backend connectivity and health
   */
  async healthCheck(): Promise<{ status: string; timestamp: number; service: string; version: string }> {
    return this.httpClient.get('/healthz');
  }

  /**
   * Perform pre-flight connection validation
   */
  async preflightCheck(options?: { timeout?: number; retryOnFailure?: boolean }): Promise<PreflightResult> {
    return this.preflightValidator.validate(options);
  }

  /**
   * Quick pre-flight check without retries
   */
  async quickPreflightCheck(): Promise<PreflightResult> {
    return this.preflightValidator.quickCheck();
  }

  /**
   * Get connection status
   */
  getConnectionStatus(): ConnectionStatus {
    const lastResult = this.preflightValidator.getLastResult();
    return lastResult?.status || ConnectionStatus.UNKNOWN;
  }

  /**
   * Check if backend is reachable
   */
  isBackendReachable(): boolean {
    return this.preflightValidator.isBackendReachable();
  }

  /**
   * Initialize service discovery
   */
  initServiceDiscovery(platform?: PlatformInfo, explicitUrl?: string): void {
    this.serviceDiscovery = new ServiceDiscovery({
      explicitUrl,
      platform,
      port: 8000,
      enableNetworkScan: platform?.isPhysicalDevice || false,
      cacheEnabled: true
    });
  }

  /**
   * Discover backend service URL
   */
  async discoverService(): Promise<DiscoveryResult> {
    if (!this.serviceDiscovery) {
      throw new Error('Service discovery not initialized. Call initServiceDiscovery() first.');
    }
    return this.serviceDiscovery.discover();
  }

  /**
   * Check backend readiness (comprehensive health check)
   */
  async readinessCheck(): Promise<any> {
    return this.httpClient.get('/readyz');
  }

  /**
   * Authenticate user with email and password with enhanced error handling
   */
  async login(email: string, password: string, options?: {
    onProgress?: (message: string) => void;
    maxAttempts?: number;
    skipPreflight?: boolean;
  }): Promise<UserResponse> {
    const maxAttempts = options?.maxAttempts || 10;
    this.authAttempts = 0;
    
    // Pre-flight check: verify backend connectivity before attempting login
    if (!options?.skipPreflight) {
      if (options?.onProgress) {
        options.onProgress("Checking server connectivity...");
      }
      
      const preflightResult = await this.preflightCheck({
        timeout: 5000,
        retryOnFailure: true
      });
      
      if (!preflightResult.backendReachable) {
        throw new Error(
          `Backend is not reachable: ${preflightResult.error || 'Unknown error'}. ${preflightResult.recommendation || ''}`
        );
      }
      
      if (preflightResult.status === ConnectionStatus.DEGRADED) {
        console.warn('Connection is degraded:', preflightResult.recommendation);
        if (options?.onProgress) {
          options.onProgress("Connection is slow, this may take longer than usual...");
        }
      }
    }

    const request: LoginRequest = { email, password };
    
    return this.executeWithEnhancedRetry(async (attemptNumber: number) => {
      this.authAttempts = attemptNumber;
      
      if (options?.onProgress) {
        const networkQuality = await this.getNetworkQuality();
        const progressMessage = UserFeedbackGenerator.generateProgressiveFeedback(
          attemptNumber,
          networkQuality.quality,
          maxAttempts
        );
        options.onProgress(progressMessage);
      }
      
      const startTime = performance.now();
      
      try {
        const response = await this.httpClient.post<UserResponse>(
          '/api/v1/auth/login',
          request
        );
        
        const duration = performance.now() - startTime;
        
        // Record successful request for timeout calibration
        this.timeoutCalibrator.recordRequest({
          duration,
          success: true,
          timestamp: Date.now()
        });

        // Store the token for future requests
        this.httpClient.setBearerToken(response.access_token);
        this.isAuthenticated = true;
        this.authAttempts = 0;
        this.lastAuthError = undefined;

        return response;
      } catch (error) {
        const duration = performance.now() - startTime;
        
        // Record failed request for timeout calibration
        this.timeoutCalibrator.recordRequest({
          duration,
          success: false,
          timestamp: Date.now()
        });
        
        throw error;
      }
    }, maxAttempts);
  }

  /**
   * Register a new user account with enhanced error handling
   */
  async register(email: string, password: string, options?: {
    onProgress?: (message: string) => void;
  }): Promise<UserResponse> {
    // First, verify backend connectivity
    if (options?.onProgress) {
      options.onProgress("Checking server connectivity...");
    }
    
    try {
      await this.healthCheck();
    } catch (healthError: any) {
      const networkQuality = await this.getNetworkQuality();
      const classification = ErrorClassifier.classifyError(healthError, networkQuality.quality);
      
      throw new ClassifiedError(healthError, classification);
    }

    const request: RegisterRequest = { email, password };
    
    if (options?.onProgress) {
      options.onProgress("Creating account...");
    }
    
    const response = await this.httpClient.post<UserResponse>(
      '/api/v1/auth/register',
      request
    );

    // Store the token for future requests (auto-login after registration)
    this.httpClient.setBearerToken(response.access_token);
    this.isAuthenticated = true;

    return response;
  }

  /**
   * Get current user profile
   */
  async getMe(): Promise<UserResponse['user']> {
    this.ensureAuthenticated();
    
    return this.httpClient.get<UserResponse['user']>('/api/v1/auth/me');
  }

  /**
   * Generate presigned URL for file upload
   */
  async presignUpload(
    filename: string,
    contentType: string,
    fileSize: number,
    idempotencyKey?: string
  ): Promise<PresignResponse> {
    this.ensureAuthenticated();

    const request: PresignRequest = {
      filename,
      content_type: contentType,
      file_size: fileSize
    };

    const options: RequestOptions = {};
    if (idempotencyKey) {
      options.idempotencyKey = idempotencyKey;
    }

    return this.httpClient.post<PresignResponse>(
      '/api/v1/uploads/presign',
      request,
      options
    );
  }

  /**
   * Upload file to presigned URL
   */
  async uploadFile(presignedUrl: string, file: File | Blob, contentType: string): Promise<void> {
    const response = await fetch(presignedUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': contentType
      },
      body: file
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
    }
  }

  /**
   * Create a new AI processing job
   */
  async createJob(
    pipeline: JobType | string,
    inputUrl: string,
    params: Record<string, any> = {},
    targetUrl?: string,
    idempotencyKey?: string
  ): Promise<JobResponse> {
    this.ensureAuthenticated();

    const request: JobCreateRequest = {
      job_type: pipeline,
      input_image_url: inputUrl,
      target_image_url: targetUrl,
      parameters: params
    };

    const options: RequestOptions = {};
    if (idempotencyKey) {
      options.idempotencyKey = idempotencyKey;
    }

    return this.httpClient.post<JobResponse>(
      '/api/v1/jobs',
      request,
      options
    );
  }

  /**
   * Get job status and progress
   */
  async getJob(jobId: string): Promise<JobStatusResponse> {
    this.ensureAuthenticated();

    return this.httpClient.get<JobStatusResponse>(`/api/v1/jobs/${jobId}`);
  }

  /**
   * List user's jobs with pagination
   */
  async listJobs(skip = 0, limit = 10): Promise<JobRead[]> {
    this.ensureAuthenticated();

    return this.httpClient.get<JobRead[]>(
      `/api/v1/jobs?skip=${skip}&limit=${limit}`
    );
  }

  /**
   * Get artifacts for a specific job
   * Note: The backend doesn't have a dedicated artifacts endpoint yet,
   * so we extract artifacts from the job response
   */
  async listArtifacts(jobId: string): Promise<Artifact[]> {
    this.ensureAuthenticated();

    const job = await this.getJob(jobId);
    
    // Convert job result to artifact format
    const artifacts: Artifact[] = [];
    if (job.result_url) {
      artifacts.push({
        id: `${jobId}_result`,
        job_id: jobId,
        artifact_type: 'image',
        output_url: job.result_url,
        created_at: job.completed_at || job.created_at
      });
    }

    return artifacts;
  }

  /**
   * Poll job status until completion
   */
  async waitForJob(
    jobId: string,
    options: {
      pollingInterval?: number;
      timeout?: number;
      onProgress?: (job: JobStatusResponse) => void;
    } = {}
  ): Promise<JobStatusResponse> {
    const { pollingInterval = 2000, timeout = 300000, onProgress } = options;
    const startTime = Date.now();

    while (Date.now() - startTime < timeout) {
      const job = await this.getJob(jobId);
      
      if (onProgress) {
        onProgress(job);
      }

      if (job.status === 'succeeded' || job.status === 'failed' || job.status === 'cancelled') {
        return job;
      }

      await this.delay(pollingInterval);
    }

    throw new Error(`Job ${jobId} timed out after ${timeout}ms`);
  }

  /**
   * Get user's plan limits and usage
   */
  async getUserLimits(): Promise<any> {
    this.ensureAuthenticated();

    return this.httpClient.get('/api/v1/jobs/limits');
  }

  /**
   * Logout - clear authentication token
   */
  logout(): void {
    this.httpClient.clearBearerToken();
    this.isAuthenticated = false;
  }

  /**
   * Check if client is authenticated
   */
  isAuth(): boolean {
    return this.isAuthenticated;
  }

  /**
   * Set authentication token manually
   */
  setAuthToken(token: string): void {
    this.httpClient.setBearerToken(token);
    this.isAuthenticated = true;
  }

  /**
   * Get current network quality assessment
   */
  async getNetworkQuality() {
    return this.httpClient.getNetworkQuality();
  }

  /**
   * Get comprehensive network diagnostics
   */
  async getNetworkDiagnostics() {
    return this.httpClient.getNetworkDiagnostics();
  }

  /**
   * Get authentication status and error information
   */
  getAuthStatus() {
    return {
      isAuthenticated: this.isAuthenticated,
      attempts: this.authAttempts,
      lastError: this.lastAuthError
    };
  }

  /**
   * Execute operation with enhanced retry logic and error classification
   */
  private async executeWithEnhancedRetry<T>(
    operation: (attemptNumber: number) => Promise<T>,
    maxAttempts: number = 10
  ): Promise<T> {
    let lastError: any;
    
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return await operation(attempt);
      } catch (error: any) {
        lastError = error;
        
        // Get current network quality for error classification
        const networkQuality = await this.getNetworkQuality();
        const circuitMetrics = this.httpClient.getCircuitBreakerMetrics();
        
        // Classify the error
        const classification = ErrorClassifier.classifyError(
          error,
          networkQuality.quality,
          circuitMetrics.state,
          attempt - 1
        );
        
        // Store classified error for status reporting
        this.lastAuthError = new ClassifiedError(error, classification);
        
        // Check if we should retry
        if (!classification.retryRecommended || attempt >= maxAttempts) {
          throw this.lastAuthError;
        }
        
        // Wait before next attempt based on network conditions
        const backoffDelay = this.calculateAdaptiveDelay(attempt, networkQuality.quality);
        console.log(`Authentication attempt ${attempt} failed, retrying in ${backoffDelay}ms:`, classification.userMessage);
        
        await this.delay(backoffDelay);
      }
    }
    
    // This shouldn't be reached, but just in case
    throw this.lastAuthError || new Error('Authentication failed after all attempts');
  }

  /**
   * Calculate adaptive delay based on attempt number and network quality
   */
  private calculateAdaptiveDelay(attemptNumber: number, networkQuality: NetworkQuality): number {
    const baseDelay = 1000; // 1 second
    let multiplier: number;
    
    switch (networkQuality) {
      case NetworkQuality.EXCELLENT:
        multiplier = attemptNumber; // Linear: 1s, 2s, 3s
        break;
      case NetworkQuality.GOOD:
        multiplier = Math.pow(2, attemptNumber - 1); // Exponential: 1s, 2s, 4s, 8s
        break;
      case NetworkQuality.FAIR:
        multiplier = attemptNumber * 1.5; // Extended: 1.5s, 3s, 4.5s, 6s
        break;
      case NetworkQuality.POOR:
      default:
        multiplier = Math.min(attemptNumber * 3, 30); // Conservative: 3s, 6s, 9s... max 30s
        break;
    }
    
    return Math.min(baseDelay * multiplier, 30000); // Cap at 30 seconds
  }

  private ensureAuthenticated(): void {
    if (!this.isAuthenticated) {
      throw new Error('Client is not authenticated. Call login() first.');
    }
  }

  private async delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Factory function for convenient SDK initialization
export function createOneShotClient(config: SdkConfig): OneShotClient {
  return new OneShotClient(config);
}

// Convenience functions for common job types
export const JobTemplates = {
  faceRestore: (inputUrl: string, params: { model?: string; enhance?: boolean } = {}) => ({
    pipeline: JobType.FACE_RESTORATION,
    inputUrl,
    params: {
      face_restore: params.model || 'gfpgan',
      enhance: params.enhance ?? true,
      ...params
    }
  }),

  faceSwap: (
    inputUrl: string,
    targetUrl: string,
    params: { blend?: number; lora?: string } = {}
  ) => ({
    pipeline: JobType.FACE_SWAP,
    inputUrl,
    targetUrl,
    params: {
      blend: params.blend ?? 0.8,
      lora: params.lora,
      ...params
    }
  }),

  upscale: (inputUrl: string, params: { scale?: number; model?: string } = {}) => ({
    pipeline: JobType.UPSCALE,
    inputUrl,
    params: {
      scale_factor: params.scale ?? 2,
      model: params.model || 'realesrgan_x4plus',
      ...params
    }
  })
};
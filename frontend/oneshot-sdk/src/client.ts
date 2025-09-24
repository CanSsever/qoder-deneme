/**
 * OneShot SDK - Main client class
 */
import { FetchHttpClient } from './http-client';
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

  constructor(config: SdkConfig) {
    this.httpClient = new FetchHttpClient(
      config.baseUrl,
      config.timeout,
      config.retryAttempts,
      config.retryDelay
    );

    // Set API key if provided
    if (config.apiKey) {
      this.httpClient.setBearerToken(config.apiKey);
      this.isAuthenticated = true;
    }
  }

  /**
   * Authenticate user with email and password
   */
  async login(email: string, password: string): Promise<UserResponse> {
    const request: LoginRequest = { email, password };
    
    const response = await this.httpClient.post<UserResponse>(
      '/api/v1/auth/login',
      request
    );

    // Store the token for future requests
    this.httpClient.setBearerToken(response.access_token);
    this.isAuthenticated = true;

    return response;
  }

  /**
   * Register a new user account
   */
  async register(email: string, password: string): Promise<UserResponse> {
    const request: RegisterRequest = { email, password };
    
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
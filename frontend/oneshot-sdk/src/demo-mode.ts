/**
 * Demo Mode and Offline Fallback System
 * Provides limited functionality when authentication fails or network is unavailable
 */

import { UserResponse, JobResponse, JobStatusResponse, JobRead, Artifact } from './types';

export interface DemoModeConfig {
  enabled: boolean;
  mockLatency: number;
  mockCredits: number;
  availableFeatures: DemoFeature[];
  limitations: DemoLimitation[];
}

export enum DemoFeature {
  MOCK_AUTHENTICATION = 'mock_authentication',
  SAMPLE_JOBS = 'sample_jobs',
  CACHED_RESULTS = 'cached_results',
  OFFLINE_BROWSING = 'offline_browsing',
  TUTORIAL_MODE = 'tutorial_mode'
}

export interface DemoLimitation {
  feature: string;
  restriction: string;
  upgradeMessage: string;
}

export interface OfflineCapability {
  canAuthenticate: boolean;
  canCreateJobs: boolean;
  canViewHistory: boolean;
  cachedData: CachedData;
}

export interface CachedData {
  lastUser?: UserResponse['user'];
  recentJobs: JobRead[];
  sampleResults: Artifact[];
  lastSyncTime: number;
}

export class DemoModeManager {
  private config: DemoModeConfig;
  private offlineData: CachedData;
  private isOfflineMode: boolean = false;

  constructor(config?: Partial<DemoModeConfig>) {
    this.config = {
      enabled: true,
      mockLatency: 1000, // 1 second simulated delay
      mockCredits: 5,
      availableFeatures: [
        DemoFeature.MOCK_AUTHENTICATION,
        DemoFeature.SAMPLE_JOBS,
        DemoFeature.CACHED_RESULTS,
        DemoFeature.TUTORIAL_MODE
      ],
      limitations: [
        {
          feature: 'Job Processing',
          restriction: 'Limited to 3 demo jobs',
          upgradeMessage: 'Sign up to process unlimited jobs'
        },
        {
          feature: 'Image Upload',
          restriction: 'Sample images only',
          upgradeMessage: 'Login to upload your own images'
        },
        {
          feature: 'Result Download',
          restriction: 'Preview only',
          upgradeMessage: 'Authenticate to download full resolution results'
        }
      ],
      ...config
    };

    this.offlineData = this.initializeOfflineData();
  }

  /**
   * Enable demo mode
   */
  enableDemoMode(): void {
    if (!this.config.enabled) {
      throw new Error('Demo mode is not enabled in configuration');
    }
    
    this.isOfflineMode = true;
    console.log('Demo mode activated with features:', this.config.availableFeatures);
  }

  /**
   * Disable demo mode
   */
  disableDemoMode(): void {
    this.isOfflineMode = false;
    console.log('Demo mode deactivated');
  }

  /**
   * Check if demo mode is active
   */
  isDemoModeActive(): boolean {
    return this.isOfflineMode && this.config.enabled;
  }

  /**
   * Get demo mode capabilities
   */
  getCapabilities(): OfflineCapability {
    return {
      canAuthenticate: this.hasFeature(DemoFeature.MOCK_AUTHENTICATION),
      canCreateJobs: this.hasFeature(DemoFeature.SAMPLE_JOBS),
      canViewHistory: this.hasFeature(DemoFeature.CACHED_RESULTS),
      cachedData: this.offlineData
    };
  }

  /**
   * Mock authentication for demo mode
   */
  async mockLogin(email: string, password: string): Promise<UserResponse> {
    if (!this.hasFeature(DemoFeature.MOCK_AUTHENTICATION)) {
      throw new Error('Mock authentication not available in demo mode');
    }

    // Simulate network delay
    await this.simulateDelay();

    // Validate demo credentials
    if (!this.isValidDemoCredentials(email, password)) {
      throw new Error('Invalid demo credentials. Try: demo@example.com / demo123');
    }

    const mockUser: UserResponse = {
      access_token: 'demo_token_' + Date.now(),
      token_type: 'Bearer',
      user: {
        id: 'demo-user-id',
        email: email,
        credits: this.config.mockCredits,
        subscription_status: 'demo',
        subscription_expires_at: undefined,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    };

    // Cache user data
    this.offlineData.lastUser = mockUser.user;
    this.updateCacheTimestamp();

    return mockUser;
  }

  /**
   * Create mock job for demo mode
   */
  async mockCreateJob(
    jobType: string,
    inputUrl: string,
    targetUrl?: string
  ): Promise<JobResponse> {
    if (!this.hasFeature(DemoFeature.SAMPLE_JOBS)) {
      throw new Error('Sample jobs not available in demo mode');
    }

    // Check demo job limits
    if (this.offlineData.recentJobs.length >= 3) {
      throw new Error('Demo mode limited to 3 jobs. Sign up for unlimited processing.');
    }

    await this.simulateDelay();

    const mockJob: JobResponse = {
      job_id: 'demo-job-' + Date.now(),
      status: 'queued',
      estimated_time: 30,
      credits_cost: 1
    };

    // Add to recent jobs cache
    this.offlineData.recentJobs.unshift({
      id: mockJob.job_id,
      user_id: this.offlineData.lastUser?.id || 'demo-user',
      job_type: jobType,
      status: 'queued',
      progress: 0,
      input_image_url: inputUrl,
      target_image_url: targetUrl,
      result_image_url: undefined,
      parameters: {},
      credits_cost: 1,
      error_message: undefined,
      created_at: new Date().toISOString(),
      completed_at: undefined
    });

    this.updateCacheTimestamp();

    // Simulate processing completion after delay
    setTimeout(() => {
      this.completeMockJob(mockJob.job_id);
    }, 5000);

    return mockJob;
  }

  /**
   * Get mock job status
   */
  async mockGetJob(jobId: string): Promise<JobStatusResponse> {
    if (!this.hasFeature(DemoFeature.SAMPLE_JOBS)) {
      throw new Error('Sample jobs not available in demo mode');
    }

    await this.simulateDelay();

    const job = this.offlineData.recentJobs.find(j => j.id === jobId);
    if (!job) {
      throw new Error('Demo job not found');
    }

    return {
      job_id: job.id,
      status: job.status,
      progress: job.progress || 0,
      result_url: job.result_image_url,
      error_message: job.error_message,
      created_at: job.created_at,
      completed_at: job.completed_at
    };
  }

  /**
   * List mock jobs
   */
  async mockListJobs(skip: number = 0, limit: number = 10): Promise<JobRead[]> {
    if (!this.hasFeature(DemoFeature.CACHED_RESULTS)) {
      throw new Error('Cached results not available in demo mode');
    }

    await this.simulateDelay();

    return this.offlineData.recentJobs.slice(skip, skip + limit);
  }

  /**
   * Get sample artifacts
   */
  async mockListArtifacts(jobId: string): Promise<Artifact[]> {
    if (!this.hasFeature(DemoFeature.CACHED_RESULTS)) {
      throw new Error('Cached results not available in demo mode');
    }

    await this.simulateDelay();

    const job = this.offlineData.recentJobs.find(j => j.id === jobId);
    if (!job || !job.result_image_url) {
      return [];
    }

    return [{
      id: `${jobId}_result`,
      job_id: jobId,
      artifact_type: 'image',
      output_url: job.result_image_url,
      created_at: job.completed_at || job.created_at
    }];
  }

  /**
   * Get demo mode limitations
   */
  getLimitations(): DemoLimitation[] {
    return this.config.limitations;
  }

  /**
   * Get upgrade message for feature
   */
  getUpgradeMessage(feature: string): string {
    const limitation = this.config.limitations.find(l => l.feature === feature);
    return limitation?.upgradeMessage || 'Sign up for full access to this feature';
  }

  /**
   * Check if feature is available in demo mode
   */
  private hasFeature(feature: DemoFeature): boolean {
    return this.config.availableFeatures.includes(feature);
  }

  /**
   * Validate demo credentials
   */
  private isValidDemoCredentials(email: string, password: string): boolean {
    const validCredentials = [
      { email: 'demo@example.com', password: 'demo123' },
      { email: 'test@demo.com', password: 'test123' },
      { email: 'guest@oneshot.ai', password: 'guest123' }
    ];

    return validCredentials.some(cred => 
      cred.email.toLowerCase() === email.toLowerCase() && 
      cred.password === password
    );
  }

  /**
   * Simulate network delay
   */
  private async simulateDelay(): Promise<void> {
    const delay = Math.random() * this.config.mockLatency;
    return new Promise(resolve => setTimeout(resolve, delay));
  }

  /**
   * Initialize offline data
   */
  private initializeOfflineData(): CachedData {
    return {
      recentJobs: [],
      sampleResults: this.generateSampleResults(),
      lastSyncTime: 0
    };
  }

  /**
   * Generate sample results for demo
   */
  private generateSampleResults(): Artifact[] {
    return [
      {
        id: 'sample_1',
        job_id: 'sample_job_1',
        artifact_type: 'image',
        output_url: 'https://example.com/sample1.jpg',
        created_at: new Date(Date.now() - 86400000).toISOString() // 1 day ago
      },
      {
        id: 'sample_2', 
        job_id: 'sample_job_2',
        artifact_type: 'image',
        output_url: 'https://example.com/sample2.jpg',
        created_at: new Date(Date.now() - 172800000).toISOString() // 2 days ago
      }
    ];
  }

  /**
   * Complete a mock job
   */
  private completeMockJob(jobId: string): void {
    const job = this.offlineData.recentJobs.find(j => j.id === jobId);
    if (job) {
      job.status = 'succeeded';
      job.progress = 100;
      job.result_image_url = `https://demo.oneshot.ai/results/${jobId}.jpg`;
      job.completed_at = new Date().toISOString();
      
      this.updateCacheTimestamp();
    }
  }

  /**
   * Update cache timestamp
   */
  private updateCacheTimestamp(): void {
    this.offlineData.lastSyncTime = Date.now();
  }

  /**
   * Clear cached data
   */
  clearCache(): void {
    this.offlineData = this.initializeOfflineData();
    console.log('Demo mode cache cleared');
  }

  /**
   * Get demo mode status info
   */
  getStatusInfo(): {
    active: boolean;
    availableFeatures: DemoFeature[];
    jobsUsed: number;
    jobsRemaining: number;
    limitations: DemoLimitation[];
  } {
    return {
      active: this.isDemoModeActive(),
      availableFeatures: this.config.availableFeatures,
      jobsUsed: this.offlineData.recentJobs.length,
      jobsRemaining: Math.max(0, 3 - this.offlineData.recentJobs.length),
      limitations: this.config.limitations
    };
  }
}

/**
 * Network diagnostics and recovery suggestions for offline mode
 */
export class OfflineRecoveryManager {
  /**
   * Diagnose network issues and suggest recovery options
   */
  static async diagnoseNetworkIssues(): Promise<{
    issues: string[];
    suggestions: string[];
    canUseDemoMode: boolean;
  }> {
    const issues: string[] = [];
    const suggestions: string[] = [];

    // Test basic connectivity
    try {
      await fetch('https://www.google.com/favicon.ico', {
        method: 'HEAD',
        mode: 'no-cors'
      });
    } catch {
      issues.push('No internet connection detected');
      suggestions.push('Check WiFi or cellular connection');
      suggestions.push('Try switching between WiFi and cellular data');
    }

    // Test DNS resolution
    try {
      await fetch('https://8.8.8.8', {
        method: 'HEAD',
        mode: 'no-cors'
      });
    } catch {
      issues.push('DNS resolution may be failing');
      suggestions.push('Try switching DNS servers (8.8.8.8, 1.1.1.1)');
    }

    if (issues.length === 0) {
      issues.push('Service may be temporarily unavailable');
      suggestions.push('Wait a few minutes and try again');
      suggestions.push('Check service status page');
    }

    suggestions.push('Use demo mode to explore features offline');

    return {
      issues,
      suggestions,
      canUseDemoMode: true
    };
  }

  /**
   * Get network recovery instructions
   */
  static getRecoveryInstructions(): string[] {
    return [
      '1. Check your internet connection',
      '2. Try switching between WiFi and cellular',
      '3. Restart your network connection',
      '4. Wait a few minutes and try again',
      '5. Use demo mode if connection issues persist',
      '6. Contact support if problem continues'
    ];
  }
}
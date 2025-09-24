/**
 * TypeScript definitions for OneShot Face Swapper API
 */

// Base API Response
export interface ApiResponse<T = any> {
  data?: T;
  error?: ApiError;
}

export interface ApiError {
  code: string;
  message: string;
  details?: any;
  status_code?: number;
}

// Authentication Types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface UserResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface User {
  id: string;
  email: string;
  credits: number;
  subscription_status: string;
  subscription_expires_at?: string;
  created_at: string;
  updated_at: string;
}

// Upload Types
export interface PresignRequest {
  filename: string;
  content_type: string;
  file_size: number;
}

export interface PresignResponse {
  presigned_url: string;
  upload_id: string;
  expires_in: number;
  max_file_size: number;
  allowed_mime_types: string[];
}

// Job Types
export interface JobCreateRequest {
  job_type: string;
  input_image_url: string;
  target_image_url?: string;
  parameters: Record<string, any>;
}

export interface JobResponse {
  job_id: string;
  status: string;
  estimated_time: number;
  credits_cost: number;
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  progress: number;
  result_url?: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface JobRead {
  id: string;
  user_id: string;
  job_type: string;
  status: string;
  progress: number;
  input_image_url: string;
  target_image_url?: string;
  result_image_url?: string;
  parameters: Record<string, any>;
  credits_cost: number;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

// Artifact Types
export interface Artifact {
  id: string;
  job_id: string;
  artifact_type: string;
  output_url: string;
  file_size?: number;
  mime_type?: string;
  created_at: string;
}

// Job Types and Statuses
export enum JobType {
  FACE_RESTORATION = 'face_restore',
  FACE_SWAP = 'face_swap',
  UPSCALE = 'upscale'
}

export enum JobStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  SUCCEEDED = 'succeeded',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

// SDK Configuration
export interface SdkConfig {
  baseUrl: string;
  apiKey?: string;
  timeout?: number;
  retryAttempts?: number;
  retryDelay?: number;
}

// HTTP Client Types
export interface HttpClient {
  get<T>(url: string, options?: RequestOptions): Promise<T>;
  post<T>(url: string, data?: any, options?: RequestOptions): Promise<T>;
  put<T>(url: string, data?: any, options?: RequestOptions): Promise<T>;
  delete<T>(url: string, options?: RequestOptions): Promise<T>;
}

export interface RequestOptions {
  headers?: Record<string, string>;
  timeout?: number;
  idempotencyKey?: string;
  retryAttempts?: number;
}

// Error Types
export enum ErrorCode {
  NETWORK_ERROR = 'NETWORK_ERROR',
  AUTHENTICATION_ERROR = 'AUTHENTICATION_ERROR',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  PAYMENT_REQUIRED = 'PAYMENT_REQUIRED',
  RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED',
  INSUFFICIENT_CREDITS = 'INSUFFICIENT_CREDITS',
  JOB_NOT_FOUND = 'JOB_NOT_FOUND',
  PARAMETER_VIOLATION = 'PARAMETER_VIOLATION',
  DAILY_LIMIT_EXCEEDED = 'DAILY_LIMIT_EXCEEDED'
}

export class OneShotError extends Error {
  constructor(
    public code: string,
    message: string,
    public statusCode?: number,
    public details?: any
  ) {
    super(message);
    this.name = 'OneShotError';
  }
}

export class NetworkError extends OneShotError {
  constructor(message: string, statusCode?: number) {
    super(ErrorCode.NETWORK_ERROR, message, statusCode);
    this.name = 'NetworkError';
  }
}

export class AuthenticationError extends OneShotError {
  constructor(message: string = 'Authentication failed') {
    super(ErrorCode.AUTHENTICATION_ERROR, message, 401);
    this.name = 'AuthenticationError';
  }
}

export class ValidationError extends OneShotError {
  constructor(message: string, details?: any) {
    super(ErrorCode.VALIDATION_ERROR, message, 422, details);
    this.name = 'ValidationError';
  }
}

export class RateLimitError extends OneShotError {
  constructor(message: string = 'Rate limit exceeded') {
    super(ErrorCode.RATE_LIMIT_EXCEEDED, message, 429);
    this.name = 'RateLimitError';
  }
}

export class PaymentRequiredError extends OneShotError {
  constructor(message: string = 'Payment required') {
    super(ErrorCode.PAYMENT_REQUIRED, message, 402);
    this.name = 'PaymentRequiredError';
  }
}
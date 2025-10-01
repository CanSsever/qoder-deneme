/**
 * Enhanced Error Classification and User Feedback System
 * Provides intelligent error classification, user-friendly messages, and recovery suggestions
 */

import { NetworkQuality, ConnectionAssessment } from './network-quality';
import { CircuitState } from './circuit-breaker';

export interface ErrorClassification {
  type: ErrorType;
  severity: ErrorSeverity;
  userMessage: string;
  technicalMessage: string;
  recoveryOptions: RecoveryOption[];
  retryRecommended: boolean;
  networkDiagnostics?: NetworkDiagnosticSuggestion[];
  recommendations: string[];
}

export enum ErrorType {
  CONNECTION_TIMEOUT = 'connection_timeout',
  SERVER_UNAVAILABLE = 'server_unavailable', 
  NETWORK_UNREACHABLE = 'network_unreachable',
  DNS_RESOLUTION = 'dns_resolution',
  SSL_TLS_ISSUES = 'ssl_tls_issues',
  AUTHENTICATION_FAILED = 'authentication_failed',
  RATE_LIMITED = 'rate_limited',
  PAYMENT_REQUIRED = 'payment_required',
  VALIDATION_ERROR = 'validation_error',
  CIRCUIT_BREAKER_OPEN = 'circuit_breaker_open',
  UNKNOWN_ERROR = 'unknown_error'
}

export enum ErrorSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export interface RecoveryOption {
  action: RecoveryAction;
  description: string;
  automated: boolean;
  estimatedTime?: string;
}

export enum RecoveryAction {
  RETRY_AUTOMATICALLY = 'retry_automatically',
  RETRY_MANUALLY = 'retry_manually',
  CHECK_NETWORK = 'check_network',
  SWITCH_NETWORK = 'switch_network',
  CONTACT_SUPPORT = 'contact_support',
  TRY_DEMO_MODE = 'try_demo_mode',
  UPDATE_APP = 'update_app',
  CLEAR_CACHE = 'clear_cache',
  WAIT_AND_RETRY = 'wait_and_retry'
}

export interface NetworkDiagnosticSuggestion {
  issue: string;
  solution: string;
  priority: 'high' | 'medium' | 'low';
}

export class ErrorClassifier {
  static classifyError(
    error: any,
    networkQuality?: NetworkQuality,
    circuitState?: CircuitState,
    previousAttempts: number = 0
  ): ErrorClassification {
    
    if (error?.name === 'AbortError' || error?.message?.includes('timeout')) {
      return this.classifyTimeoutError(error, networkQuality, previousAttempts);
    }
    
    if (error?.status >= 500) {
      return this.classifyServerError(error, previousAttempts);
    }
    
    if (error?.status === 401) {
      return this.classifyAuthenticationError(error);
    }
    
    if (error?.status === 429) {
      return this.classifyRateLimitError(error);
    }
    
    if (error?.message?.includes('fetch failed')) {
      return this.classifyNetworkError(error, networkQuality);
    }
    
    if (circuitState === CircuitState.OPEN) {
      return this.classifyCircuitBreakerError(error);
    }
    
    return this.classifyUnknownError(error);
  }
  
  private static classifyTimeoutError(
    error: any,
    networkQuality?: NetworkQuality,
    previousAttempts: number = 0
  ): ErrorClassification {
    const isRepeatedTimeout = previousAttempts > 2;
    
    let userMessage = "Connection taking longer than expected";
    let severity = ErrorSeverity.MEDIUM;
    
    if (networkQuality === NetworkQuality.POOR) {
      userMessage = "Slow connection detected. Extending timeout and retrying...";
      severity = ErrorSeverity.HIGH;
    } else if (isRepeatedTimeout) {
      userMessage = "Repeated connection timeouts. There may be a server issue.";
      severity = ErrorSeverity.HIGH;
    }
    
    return {
      type: ErrorType.CONNECTION_TIMEOUT,
      severity,
      userMessage,
      technicalMessage: error.message || 'Request timeout',
      recoveryOptions: [
        {
          action: RecoveryAction.RETRY_AUTOMATICALLY,
          description: "Retrying with extended timeout",
          automated: true,
          estimatedTime: "30-60 seconds"
        },
        {
          action: RecoveryAction.CHECK_NETWORK,
          description: "Check your internet connection",
          automated: false
        }
      ],
      retryRecommended: !isRepeatedTimeout,
      networkDiagnostics: networkQuality === NetworkQuality.POOR ? [{
        issue: "Poor network quality detected",
        solution: "Try switching to a faster network connection",
        priority: 'high'
      }] : [],
      recommendations: ['Check your internet connection', 'Try switching networks']
    };
  }
  
  private static classifyServerError(error: any, previousAttempts: number): ErrorClassification {
    const isRepeatedError = previousAttempts > 3;
    
    return {
      type: ErrorType.SERVER_UNAVAILABLE,
      severity: isRepeatedError ? ErrorSeverity.HIGH : ErrorSeverity.MEDIUM,
      userMessage: isRepeatedError 
        ? "Server is experiencing issues. Please try again later."
        : "Server temporarily unavailable. Retrying...",
      technicalMessage: `HTTP ${error.status}: ${error.message}`,
      recoveryOptions: [
        {
          action: RecoveryAction.RETRY_AUTOMATICALLY,
          description: "Automatic retry with backoff",
          automated: true,
          estimatedTime: "10-30 seconds"
        },
        {
          action: RecoveryAction.TRY_DEMO_MODE,
          description: "Try demo mode while server recovers",
          automated: false
        }
      ],
      retryRecommended: true,
      recommendations: ['Wait and retry automatically', 'Try demo mode']
    };
  }
  
  private static classifyAuthenticationError(error: any): ErrorClassification {
    return {
      type: ErrorType.AUTHENTICATION_FAILED,
      severity: ErrorSeverity.HIGH,
      userMessage: "Login failed. Please check your credentials.",
      technicalMessage: error.message || 'Authentication failed',
      recoveryOptions: [
        {
          action: RecoveryAction.RETRY_MANUALLY,
          description: "Try logging in again",
          automated: false
        }
      ],
      retryRecommended: false,
      recommendations: ['Check your credentials', 'Reset password if needed']
    };
  }
  
  private static classifyRateLimitError(error: any): ErrorClassification {
    return {
      type: ErrorType.RATE_LIMITED,
      severity: ErrorSeverity.MEDIUM,
      userMessage: "Too many requests. Please wait a moment and try again.",
      technicalMessage: 'Rate limit exceeded',
      recoveryOptions: [
        {
          action: RecoveryAction.WAIT_AND_RETRY,
          description: "Wait and retry automatically",
          automated: true,
          estimatedTime: "30-60 seconds"
        }
      ],
      retryRecommended: true,
      recommendations: ['Wait before retrying', 'Reduce request frequency']
    };
  }
  
  private static classifyNetworkError(error: any, networkQuality?: NetworkQuality): ErrorClassification {
    return {
      type: ErrorType.NETWORK_UNREACHABLE,
      severity: ErrorSeverity.HIGH,
      userMessage: "Cannot reach server. Please check your internet connection.",
      technicalMessage: error.message || 'Network error',
      recoveryOptions: [
        {
          action: RecoveryAction.CHECK_NETWORK,
          description: "Check internet connection",
          automated: false
        },
        {
          action: RecoveryAction.RETRY_AUTOMATICALLY,
          description: "Retry when connection improves",
          automated: true,
          estimatedTime: "30 seconds"
        }
      ],
      retryRecommended: true,
      networkDiagnostics: [{
        issue: "Cannot reach server",
        solution: "Check your internet connection",
        priority: 'high'
      }],
      recommendations: ['Check internet connection', 'Try different network']
    };
  }
  
  private static classifyCircuitBreakerError(error: any): ErrorClassification {
    return {
      type: ErrorType.CIRCUIT_BREAKER_OPEN,
      severity: ErrorSeverity.MEDIUM,
      userMessage: "Service temporarily unavailable due to repeated failures. Waiting to retry...",
      technicalMessage: error.message || 'Circuit breaker open',
      recoveryOptions: [
        {
          action: RecoveryAction.WAIT_AND_RETRY,
          description: "Wait for automatic retry",
          automated: true,
          estimatedTime: "30-60 seconds"
        }
      ],
      retryRecommended: true,
      recommendations: ['Wait for service recovery', 'Try demo mode']
    };
  }
  
  private static classifyUnknownError(error: any): ErrorClassification {
    return {
      type: ErrorType.UNKNOWN_ERROR,
      severity: ErrorSeverity.MEDIUM,
      userMessage: "An unexpected error occurred. Please try again.",
      technicalMessage: error.message || 'Unknown error',
      recoveryOptions: [
        {
          action: RecoveryAction.RETRY_MANUALLY,
          description: "Try again",
          automated: false
        }
      ],
      retryRecommended: true,
      recommendations: ['Try again', 'Contact support if persists']
    };
  }
}

export class UserFeedbackGenerator {
  static generateProgressiveFeedback(
    attemptNumber: number,
    networkQuality: NetworkQuality,
    totalAttempts: number
  ): string {
    if (attemptNumber === 1) {
      return "Connecting to server...";
    }
    
    if (attemptNumber === 2) {
      return "Checking connection quality...";
    }
    
    if (attemptNumber <= 3) {
      return `Authenticating credentials... (attempt ${attemptNumber}/${totalAttempts})`;
    }
    
    if (networkQuality === NetworkQuality.POOR) {
      return "Poor connection detected, extending timeout...";
    }
    
    if (attemptNumber > totalAttempts - 2) {
      return "Making final attempt with maximum timeout...";
    }
    
    return `Connection slower than expected, retrying... (${attemptNumber}/${totalAttempts})`;
  }
}

export class ClassifiedError extends Error {
  public readonly classification: ErrorClassification;
  public readonly originalError: any;
  
  constructor(originalError: any, classification: ErrorClassification) {
    super(classification.userMessage);
    this.name = 'ClassifiedError';
    this.classification = classification;
    this.originalError = originalError;
  }
  
  getUserMessage(): string {
    return this.classification.userMessage;
  }
  
  shouldRetry(): boolean {
    return this.classification.retryRecommended;
  }
}
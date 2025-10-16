/**
 * OneShot SDK - Main entry point
 */

// Export main client
export { OneShotClient, createOneShotClient, JobTemplates } from './client';

// Export HTTP client for advanced use cases
export { FetchHttpClient } from './http-client';

// Export network quality and monitoring
export { NetworkQualityAssessment, NetworkQuality } from './network-quality';
export { ConnectionHealthMonitor, AlertLevel, IssueType, ConnectionHealthStatus } from './connection-monitor';
export { PreflightValidator, ConnectionStatus, PreflightResult } from './preflight-validator';
export { ServiceDiscovery, DiscoveryResult, PlatformInfo } from './service-discovery';
export { AdaptiveTimeoutCalibrator } from './adaptive-timeout';
export { ErrorClassifier, UserFeedbackGenerator, ClassifiedError } from './error-classification';
export { CircuitBreaker, circuitBreakerManager } from './circuit-breaker';

// Export all types
export * from './types';

// Default export for convenience
export { OneShotClient as default } from './client';

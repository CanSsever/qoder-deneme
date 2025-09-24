/**
 * OneShot SDK - Main entry point
 */

// Export main client
export { OneShotClient, createOneShotClient, JobTemplates } from './client';

// Export HTTP client for advanced use cases
export { FetchHttpClient } from './http-client';

// Export all types
export * from './types';

// Default export for convenience
export { OneShotClient as default } from './client';
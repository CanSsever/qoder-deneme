/**
 * Network diagnostics and connectivity testing utilities
 */
import { oneShotClient, CONFIG } from './client';

export interface ConnectivityTestResult {
  success: boolean;
  latency?: number;
  error?: string;
  timestamp: number;
}

export interface NetworkInfo {
  apiUrl: string;
  timeout: number;
  retryAttempts: number;
  userAgent: string;
  online: boolean;
  timestamp: number;
}

export interface DiagnosticReport {
  networkInfo: NetworkInfo;
  connectivityTest: ConnectivityTestResult;
  recommendations: string[];
}

export class NetworkDiagnostics {
  /**
   * Test basic connectivity to the backend with detailed timing
   */
  static async testConnectivity(): Promise<ConnectivityTestResult> {
    const startTime = Date.now();
    
    try {
      const response = await oneShotClient.healthCheck();
      const latency = Date.now() - startTime;
      
      return {
        success: true,
        latency,
        timestamp: Date.now()
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Connection test failed',
        timestamp: Date.now()
      };
    }
  }

  /**
   * Get comprehensive network information
   */
  static getNetworkInfo(): NetworkInfo {
    return {
      apiUrl: CONFIG.API_URL,
      timeout: CONFIG.API_TIMEOUT,
      retryAttempts: 5,
      userAgent: navigator.userAgent,
      online: navigator.onLine,
      timestamp: Date.now()
    };
  }

  /**
   * Run a comprehensive diagnostic report
   */
  static async generateDiagnosticReport(): Promise<DiagnosticReport> {
    const networkInfo = this.getNetworkInfo();
    const connectivityTest = await this.testConnectivity();
    const recommendations = this.generateRecommendations(networkInfo, connectivityTest);

    return {
      networkInfo,
      connectivityTest,
      recommendations
    };
  }

  /**
   * Generate troubleshooting recommendations based on test results
   */
  static generateRecommendations(
    networkInfo: NetworkInfo,
    connectivityTest: ConnectivityTestResult
  ): string[] {
    const recommendations: string[] = [];

    // Check online status
    if (!networkInfo.online) {
      recommendations.push('Device appears to be offline. Check your internet connection.');
    }

    // Check connectivity test results
    if (!connectivityTest.success) {
      const error = connectivityTest.error || '';
      
      if (error.includes('timeout')) {
        recommendations.push('Connection timeout detected. Try connecting to a faster network.');
        recommendations.push('If using mobile data, try switching to WiFi.');
      } else if (error.includes('Network connection failed') || error.includes('Failed to fetch')) {
        recommendations.push('Cannot reach the server. Check if the backend is running.');
        recommendations.push('Verify that your device and server are on the same network.');
      } else if (error.includes('Unable to reach server')) {
        recommendations.push('Server may be down or unreachable.');
        recommendations.push('Check the API URL configuration in your app settings.');
      } else {
        recommendations.push('Unknown network error. Try restarting the app.');
      }
    } else {
      // Connection successful - check latency
      const latency = connectivityTest.latency || 0;
      
      if (latency > 5000) {
        recommendations.push('High latency detected (>5s). Consider using a faster network.');
      } else if (latency > 2000) {
        recommendations.push('Moderate latency detected. Connection may be slow.');
      } else {
        recommendations.push('Connection is working well!');
      }
    }

    // Check API URL configuration
    if (networkInfo.apiUrl.includes('localhost') || networkInfo.apiUrl.includes('127.0.0.1')) {
      recommendations.push('Using localhost address. Make sure you\'re testing on the same device as the server.');
    }

    return recommendations;
  }

  /**
   * Test authentication endpoint specifically
   */
  static async testAuthEndpoint(): Promise<ConnectivityTestResult> {
    const startTime = Date.now();
    
    try {
      // Try to make a request to the auth endpoint with invalid credentials
      // This should return a 401 error, which means the endpoint is reachable
      await oneShotClient.login('test@example.com', 'invalid');
      
      // If we get here without error, something is wrong
      return {
        success: false,
        error: 'Unexpected response from auth endpoint',
        timestamp: Date.now()
      };
    } catch (error: any) {
      const latency = Date.now() - startTime;
      
      // Check if we got a proper authentication error (means endpoint is working)
      if (error.message && error.message.includes('Invalid email or password')) {
        return {
          success: true,
          latency,
          timestamp: Date.now()
        };
      }
      
      // Network or other error
      return {
        success: false,
        error: error.message || 'Auth endpoint test failed',
        timestamp: Date.now()
      };
    }
  }

  /**
   * Get user-friendly error message based on error type
   */
  static getUserFriendlyErrorMessage(error: any): {
    title: string;
    message: string;
    actions: Array<{ text: string; action?: string }>;
  } {
    const errorMessage = error?.message || '';

    if (errorMessage.includes('Unable to reach server')) {
      return {
        title: 'Connection Problem',
        message: 'Cannot connect to the server. Please check your internet connection and try again.',
        actions: [
          { text: 'Test Connection', action: 'test_connection' },
          { text: 'Try Demo Mode', action: 'demo_mode' },
          { text: 'Retry', action: 'retry' },
          { text: 'Cancel' }
        ]
      };
    }

    if (errorMessage.includes('timeout')) {
      return {
        title: 'Connection Timeout',
        message: 'The server is taking too long to respond. This might be due to a slow network connection.',
        actions: [
          { text: 'Retry', action: 'retry' },
          { text: 'Try Demo Mode', action: 'demo_mode' },
          { text: 'Cancel' }
        ]
      };
    }

    if (errorMessage.includes('Invalid email or password')) {
      return {
        title: 'Login Failed',
        message: 'Invalid email or password. Please check your credentials and try again.',
        actions: [
          { text: 'Try Again', action: 'retry' },
          { text: 'Cancel' }
        ]
      };
    }

    if (errorMessage.includes('Network connection failed')) {
      return {
        title: 'Network Error',
        message: 'Unable to connect to the internet. Please check your network connection.',
        actions: [
          { text: 'Check Network', action: 'network_info' },
          { text: 'Retry', action: 'retry' },
          { text: 'Cancel' }
        ]
      };
    }

    // Generic error
    return {
      title: 'Error',
      message: errorMessage || 'An unexpected error occurred. Please try again.',
      actions: [
        { text: 'Retry', action: 'retry' },
        { text: 'Cancel' }
      ]
    };
  }
}

export default NetworkDiagnostics;
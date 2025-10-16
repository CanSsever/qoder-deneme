/**
 * Authentication module with enhanced error handling
 * 
 * Provides meaningful, actionable error messages for common failure scenarios
 */
import ApiClient from '../../api/client';
import { resolveBaseURL, getPlatformTimeout, getPlatformRetryAttempts } from '../../config/api';

// Create singleton API client instance
const apiClient = new ApiClient({
  baseURL: resolveBaseURL(),
  timeout: getPlatformTimeout(),
  retries: getPlatformRetryAttempts(),
});

export interface LoginResponse {
  access_token: string;
  user: {
    id: string;
    email: string;
    credits: number;
  };
}

export interface RegisterResponse extends LoginResponse {}

/**
 * Login with enhanced error messages
 */
export async function login(email: string, password: string): Promise<LoginResponse> {
  try {
    const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', {
      email,
      password,
    });

    // Store token for future requests
    if (response.access_token) {
      apiClient.setBearerToken(response.access_token);
    }

    return response;
  } catch (error: any) {
    console.error('[Auth] Login error:', error);

    // Connection timeout
    if (error?.name === 'AbortError' || error?.message?.includes('aborted')) {
      throw new Error(
        'Sunucuya bağlanılamadı (zaman aşımı). Ağ bağlantınızı, DNS ayarlarınızı ve URL eşlemelerini kontrol edin.'
      );
    }

    // Network connectivity issues
    if (
      error?.message?.toLowerCase?.().includes('network') ||
      error?.message?.toLowerCase?.().includes('fetch') ||
      error?.message?.toLowerCase?.().includes('failed to connect')
    ) {
      throw new Error(
        'Ağ bağlantı sorunu tespit edildi. Sunucu adresini ve internet bağlantınızı doğrulayın.'
      );
    }

    // Authentication errors (401)
    if (error?.message?.includes('401') || error?.message?.includes('Invalid')) {
      throw new Error('Geçersiz e-posta veya şifre. Lütfen kimlik bilgilerinizi kontrol edin.');
    }

    // Rate limiting (429)
    if (error?.message?.includes('429')) {
      throw new Error('Çok fazla giriş denemesi. Lütfen birkaç dakika sonra tekrar deneyin.');
    }

    // Server errors (5xx)
    if (error?.message?.includes('500') || error?.message?.includes('502') || error?.message?.includes('503')) {
      throw new Error('Sunucu geçici olarak kullanılamıyor. Lütfen daha sonra tekrar deneyin.');
    }

    // Generic error
    throw new Error(
      error?.message || 'Giriş başarısız. Lütfen tekrar deneyin.'
    );
  }
}

/**
 * Register new user account
 */
export async function register(email: string, password: string): Promise<RegisterResponse> {
  try {
    const response = await apiClient.post<RegisterResponse>('/api/v1/auth/register', {
      email,
      password,
    });

    // Store token for future requests
    if (response.access_token) {
      apiClient.setBearerToken(response.access_token);
    }

    return response;
  } catch (error: any) {
    console.error('[Auth] Registration error:', error);

    // Connection timeout
    if (error?.name === 'AbortError' || error?.message?.includes('aborted')) {
      throw new Error(
        'Sunucuya bağlanılamadı (zaman aşımı). Ağ bağlantınızı kontrol edin.'
      );
    }

    // Network issues
    if (
      error?.message?.toLowerCase?.().includes('network') ||
      error?.message?.toLowerCase?.().includes('fetch')
    ) {
      throw new Error(
        'Ağ bağlantı sorunu tespit edildi. İnternet bağlantınızı doğrulayın.'
      );
    }

    // Email already exists (422 or 409)
    if (error?.message?.includes('422') || error?.message?.includes('409') || error?.message?.includes('exists')) {
      throw new Error('Bu e-posta adresi zaten kullanılıyor. Farklı bir e-posta deneyin.');
    }

    // Validation errors
    if (error?.message?.includes('validation') || error?.message?.includes('invalid')) {
      throw new Error('Geçersiz e-posta veya şifre formatı. Lütfen kontrol edin.');
    }

    // Generic error
    throw new Error(
      error?.message || 'Kayıt başarısız. Lütfen tekrar deneyin.'
    );
  }
}

/**
 * Logout - clear authentication
 */
export function logout(): void {
  apiClient.clearBearerToken();
}

/**
 * Export the configured API client for use in other modules
 */
export { apiClient };

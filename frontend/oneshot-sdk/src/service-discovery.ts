/**
 * Intelligent Service Discovery
 * Automatically detects and validates correct backend URL
 */

export interface PlatformInfo {
  os: 'android' | 'ios' | 'web' | 'unknown';
  isEmulator: boolean;
  isSimulator: boolean;
  isPhysicalDevice: boolean;
}

export interface DiscoveryResult {
  url: string;
  source: 'explicit' | 'cached' | 'platform-default' | 'network-scan' | 'fallback';
  validated: boolean;
  latency?: number;
  timestamp: number;
}

export interface CachedIPEntry {
  ip: string;
  port: number;
  networkSSID?: string;
  lastSuccessful: number;
  successCount: number;
  isVerified: boolean;
}

export interface ServiceDiscoveryConfig {
  explicitUrl?: string;
  port?: number;
  platform?: PlatformInfo;
  enableNetworkScan?: boolean;
  cacheEnabled?: boolean;
  validationTimeout?: number;
}

export class ServiceDiscovery {
  private config: ServiceDiscoveryConfig;
  private cachedIPs: Map<string, CachedIPEntry> = new Map();
  private lastDiscoveryResult?: DiscoveryResult;
  private storageKey = '@oneshot_cached_ips';

  constructor(config: ServiceDiscoveryConfig = {}) {
    this.config = {
      port: 8000,
      enableNetworkScan: true,
      cacheEnabled: true,
      validationTimeout: 5000,
      ...config
    };
  }

  /**
   * Discover backend service URL
   */
  async discover(): Promise<DiscoveryResult> {
    // Step 1: Check for explicit URL override
    if (this.config.explicitUrl && this.config.explicitUrl.trim()) {
      const result = await this.validateUrl(this.config.explicitUrl.trim(), 'explicit');
      if (result.validated) {
        this.lastDiscoveryResult = result;
        return result;
      }
      console.warn('Explicit URL failed validation, falling back to discovery');
    }

    // Step 2: Try cached IP if available
    if (this.config.cacheEnabled) {
      const cachedResult = await this.tryCachedIP();
      if (cachedResult) {
        this.lastDiscoveryResult = cachedResult;
        return cachedResult;
      }
    }

    // Step 3: Use platform-specific defaults
    const platformUrl = this.getPlatformDefaultUrl();
    const platformResult = await this.validateUrl(platformUrl, 'platform-default');
    if (platformResult.validated) {
      this.cacheSuccessfulIP(platformUrl);
      this.lastDiscoveryResult = platformResult;
      return platformResult;
    }

    // Step 4: Network scan for physical devices
    if (this.config.platform?.isPhysicalDevice && this.config.enableNetworkScan) {
      const scanResult = await this.scanNetwork();
      if (scanResult) {
        this.cacheSuccessfulIP(scanResult.url);
        this.lastDiscoveryResult = scanResult;
        return scanResult;
      }
    }

    // Step 5: Fallback to last known good or default
    const fallbackUrl = this.getFallbackUrl();
    const fallbackResult: DiscoveryResult = {
      url: fallbackUrl,
      source: 'fallback',
      validated: false,
      timestamp: Date.now()
    };

    this.lastDiscoveryResult = fallbackResult;
    return fallbackResult;
  }

  /**
   * Get platform-specific default URL
   */
  private getPlatformDefaultUrl(): string {
    const port = this.config.port || 8000;
    const platform = this.config.platform;

    if (!platform) {
      return `http://localhost:${port}`;
    }

    if (platform.os === 'android') {
      if (platform.isEmulator) {
        // Android emulator: 10.0.2.2 maps to host localhost
        return `http://10.0.2.2:${port}`;
      } else {
        // Physical Android device: need LAN IP
        return this.getCommonLANIP(port);
      }
    } else if (platform.os === 'ios') {
      if (platform.isSimulator) {
        // iOS simulator: use localhost
        return `http://localhost:${port}`;
      } else {
        // Physical iOS device: need LAN IP
        return this.getCommonLANIP(port);
      }
    } else if (platform.os === 'web') {
      return `http://localhost:${port}`;
    }

    // Unknown platform: default to localhost
    return `http://localhost:${port}`;
  }

  /**
   * Get common LAN IP pattern (fallback for physical devices)
   */
  private getCommonLANIP(port: number): string {
    // Try most common router default gateway patterns
    const commonIPs = [
      '192.168.1.1',
      '192.168.0.1',
      '192.168.100.1',
      '10.0.0.1'
    ];

    // Return first common IP (will be validated)
    return `http://${commonIPs[0]}:${port}`;
  }

  /**
   * Try cached IP addresses
   */
  private async tryCachedIP(): Promise<DiscoveryResult | null> {
    await this.loadCachedIPs();

    if (this.cachedIPs.size === 0) {
      return null;
    }

    // Sort by success count and recency
    const sortedIPs = Array.from(this.cachedIPs.values())
      .filter(entry => entry.isVerified)
      .sort((a, b) => {
        // Prioritize recent and frequently successful IPs
        const scoreA = a.successCount + (Date.now() - a.lastSuccessful < 86400000 ? 10 : 0);
        const scoreB = b.successCount + (Date.now() - b.lastSuccessful < 86400000 ? 10 : 0);
        return scoreB - scoreA;
      });

    // Try top cached IPs
    for (const entry of sortedIPs.slice(0, 3)) {
      const url = `http://${entry.ip}:${entry.port}`;
      const result = await this.validateUrl(url, 'cached');
      
      if (result.validated) {
        // Update cache with successful validation
        entry.lastSuccessful = Date.now();
        entry.successCount += 1;
        await this.saveCachedIPs();
        return result;
      }
    }

    return null;
  }

  /**
   * Scan network for backend service
   */
  private async scanNetwork(): Promise<DiscoveryResult | null> {
    const port = this.config.port || 8000;
    
    // Common LAN IP ranges to scan
    const candidateIPs = this.generateCandidateIPs();

    console.log(`Scanning ${candidateIPs.length} candidate IPs for backend service...`);

    // Try candidates in parallel (with concurrency limit)
    const concurrency = 5;
    for (let i = 0; i < candidateIPs.length; i += concurrency) {
      const batch = candidateIPs.slice(i, i + concurrency);
      const results = await Promise.allSettled(
        batch.map(ip => this.validateUrl(`http://${ip}:${port}`, 'network-scan'))
      );

      // Return first successful result
      for (const result of results) {
        if (result.status === 'fulfilled' && result.value.validated) {
          return result.value;
        }
      }
    }

    return null;
  }

  /**
   * Generate candidate IP addresses to scan
   */
  private generateCandidateIPs(): string[] {
    const candidates: string[] = [];

    // Common LAN ranges
    const ranges = [
      { base: '192.168.1', start: 1, end: 50 },
      { base: '192.168.0', start: 1, end: 50 },
      { base: '192.168.100', start: 1, end: 50 },
      { base: '10.0.0', start: 1, end: 50 }
    ];

    for (const range of ranges) {
      for (let i = range.start; i <= range.end; i++) {
        candidates.push(`${range.base}.${i}`);
      }
    }

    return candidates;
  }

  /**
   * Validate if URL is reachable
   */
  private async validateUrl(url: string, source: DiscoveryResult['source']): Promise<DiscoveryResult> {
    const startTime = performance.now();
    const timeout = this.config.validationTimeout || 5000;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const response = await fetch(`${url}/healthz`, {
        method: 'HEAD',
        signal: controller.signal,
        headers: {
          'Cache-Control': 'no-cache'
        }
      });

      clearTimeout(timeoutId);
      const latency = Math.round(performance.now() - startTime);

      return {
        url,
        source,
        validated: response.ok,
        latency,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        url,
        source,
        validated: false,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Cache successful IP address
   */
  private cacheSuccessfulIP(url: string): void {
    if (!this.config.cacheEnabled) return;

    try {
      const urlObj = new URL(url);
      const ip = urlObj.hostname;
      const port = parseInt(urlObj.port) || 80;

      const existing = this.cachedIPs.get(ip);
      
      if (existing) {
        existing.lastSuccessful = Date.now();
        existing.successCount += 1;
        existing.isVerified = true;
      } else {
        this.cachedIPs.set(ip, {
          ip,
          port,
          lastSuccessful: Date.now(),
          successCount: 1,
          isVerified: true
        });
      }

      this.saveCachedIPs();
    } catch (error) {
      console.warn('Failed to cache IP:', error);
    }
  }

  /**
   * Get fallback URL
   */
  private getFallbackUrl(): string {
    // Try to get last successful URL from cache
    const sortedIPs = Array.from(this.cachedIPs.values())
      .sort((a, b) => b.lastSuccessful - a.lastSuccessful);

    if (sortedIPs.length > 0) {
      const latest = sortedIPs[0];
      return `http://${latest.ip}:${latest.port}`;
    }

    // Final fallback to localhost
    return `http://localhost:${this.config.port || 8000}`;
  }

  /**
   * Load cached IPs from storage
   */
  private async loadCachedIPs(): Promise<void> {
    if (typeof window === 'undefined') return;

    try {
      const stored = localStorage.getItem(this.storageKey);
      if (stored) {
        const entries: CachedIPEntry[] = JSON.parse(stored);
        
        // Filter out stale entries (older than 7 days)
        const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
        const validEntries = entries.filter(entry => entry.lastSuccessful > cutoff);
        
        this.cachedIPs.clear();
        validEntries.forEach(entry => {
          this.cachedIPs.set(entry.ip, entry);
        });
      }
    } catch (error) {
      console.warn('Failed to load cached IPs:', error);
    }
  }

  /**
   * Save cached IPs to storage
   */
  private async saveCachedIPs(): Promise<void> {
    if (typeof window === 'undefined') return;

    try {
      const entries = Array.from(this.cachedIPs.values());
      localStorage.setItem(this.storageKey, JSON.stringify(entries));
    } catch (error) {
      console.warn('Failed to save cached IPs:', error);
    }
  }

  /**
   * Clear IP cache
   */
  async clearCache(): Promise<void> {
    this.cachedIPs.clear();
    if (typeof window !== 'undefined') {
      localStorage.removeItem(this.storageKey);
    }
  }

  /**
   * Get last discovery result
   */
  getLastResult(): DiscoveryResult | undefined {
    return this.lastDiscoveryResult;
  }

  /**
   * Force refresh discovery
   */
  async refresh(): Promise<DiscoveryResult> {
    this.lastDiscoveryResult = undefined;
    return this.discover();
  }

  /**
   * Get diagnostic information
   */
  getDiagnostics(): {
    lastResult?: DiscoveryResult;
    cachedIPCount: number;
    cachedIPs: CachedIPEntry[];
    platformInfo?: PlatformInfo;
  } {
    return {
      lastResult: this.lastDiscoveryResult,
      cachedIPCount: this.cachedIPs.size,
      cachedIPs: Array.from(this.cachedIPs.values()),
      platformInfo: this.config.platform
    };
  }
}

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  Modal,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { oneShotClient } from '../utils/client';
import { ConnectionStatus } from 'oneshot-sdk';

interface NetworkDiagnosticsModalProps {
  visible: boolean;
  onClose: () => void;
}

interface DiagnosticData {
  connectionStatus: ConnectionStatus;
  apiUrl: string;
  timeout: number;
  retryAttempts: number;
  lastCheckLatency?: number;
  networkQuality?: string;
  backendReachable: boolean;
  recommendation?: string;
}

export default function NetworkDiagnosticsModal({ visible, onClose }: NetworkDiagnosticsModalProps) {
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [diagnosticData, setDiagnosticData] = useState<DiagnosticData | null>(null);
  const [testResults, setTestResults] = useState<string[]>([]);

  useEffect(() => {
    if (visible) {
      loadDiagnostics();
    }
  }, [visible]);

  const loadDiagnostics = async () => {
    setLoading(true);
    try {
      const status = oneShotClient.getConnectionStatus();
      const networkQuality = await oneShotClient.getNetworkQuality();
      const preflightResult = oneShotClient['preflightValidator']?.getLastResult();

      setDiagnosticData({
        connectionStatus: status,
        apiUrl: oneShotClient['baseUrl'] || 'Unknown',
        timeout: oneShotClient['timeoutCalibrator']?.getCurrentTimeout() || 30000,
        retryAttempts: 5,
        lastCheckLatency: preflightResult?.latency,
        networkQuality: networkQuality?.quality || 'Unknown',
        backendReachable: preflightResult?.backendReachable || false,
        recommendation: preflightResult?.recommendation
      });
    } catch (error) {
      console.error('Failed to load diagnostics:', error);
    } finally {
      setLoading(false);
    }
  };

  const runConnectionTest = async () => {
    setTesting(true);
    setTestResults([]);
    const results: string[] = [];

    try {
      // Test 1: Pre-flight check
      results.push('Running pre-flight check...');
      setTestResults([...results]);
      
      const preflightResult = await oneShotClient.preflightCheck({
        timeout: 5000,
        retryOnFailure: false
      });

      if (preflightResult.backendReachable) {
        results.push(`✓ Backend reachable (${preflightResult.latency}ms)`);
      } else {
        results.push(`✗ Backend not reachable: ${preflightResult.error}`);
      }
      setTestResults([...results]);

      // Test 2: Health check
      results.push('Testing health endpoint...');
      setTestResults([...results]);
      
      try {
        const healthStart = performance.now();
        await oneShotClient.healthCheck();
        const healthLatency = Math.round(performance.now() - healthStart);
        results.push(`✓ Health check passed (${healthLatency}ms)`);
      } catch (error: any) {
        results.push(`✗ Health check failed: ${error.message}`);
      }
      setTestResults([...results]);

      // Test 3: Network quality assessment
      results.push('Assessing network quality...');
      setTestResults([...results]);
      
      const networkQuality = await oneShotClient.getNetworkQuality();
      results.push(`Network Quality: ${networkQuality.quality.toUpperCase()}`);
      results.push(`- Latency: ${networkQuality.metrics.latency}ms`);
      results.push(`- Stability: ${networkQuality.metrics.stability}%`);
      results.push(`- Error Rate: ${networkQuality.metrics.errorRate}%`);
      setTestResults([...results]);

      // Test 4: Timeout calibration info
      const calibrationData = oneShotClient['timeoutCalibrator']?.getCalibrationData();
      if (calibrationData) {
        results.push(`Calibrated Timeout: ${calibrationData.currentTimeout}ms`);
        results.push(`Success Rate: ${(calibrationData.successRate * 100).toFixed(1)}%`);
      }
      setTestResults([...results]);

      results.push('');
      results.push('Test completed successfully!');
      setTestResults([...results]);

      Alert.alert('Test Complete', 'Connection tests completed. See results above.');
    } catch (error: any) {
      results.push(`✗ Test failed: ${error.message}`);
      setTestResults([...results]);
      Alert.alert('Test Failed', error.message);
    } finally {
      setTesting(false);
      await loadDiagnostics();
    }
  };

  const getStatusColor = (status: ConnectionStatus): string => {
    switch (status) {
      case ConnectionStatus.CONNECTED:
        return '#10B981'; // Green
      case ConnectionStatus.DEGRADED:
        return '#F59E0B'; // Orange
      case ConnectionStatus.DISCONNECTED:
        return '#EF4444'; // Red
      case ConnectionStatus.CHECKING:
        return '#3B82F6'; // Blue
      default:
        return '#6B7280'; // Gray
    }
  };

  const getStatusIcon = (status: ConnectionStatus): string => {
    switch (status) {
      case ConnectionStatus.CONNECTED:
        return '●';
      case ConnectionStatus.DEGRADED:
        return '◐';
      case ConnectionStatus.DISCONNECTED:
        return '○';
      case ConnectionStatus.CHECKING:
        return '◌';
      default:
        return '?';
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Network Diagnostics</Text>
          <TouchableOpacity style={styles.closeButton} onPress={onClose}>
            <Text style={styles.closeButtonText}>Close</Text>
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.content}>
          {loading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color="#2563EB" />
              <Text style={styles.loadingText}>Loading diagnostics...</Text>
            </View>
          ) : (
            <>
              {/* Connection Status */}
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Connection Status</Text>
                <View style={styles.statusRow}>
                  <Text
                    style={[
                      styles.statusIndicator,
                      { color: diagnosticData ? getStatusColor(diagnosticData.connectionStatus) : '#6B7280' }
                    ]}
                  >
                    {diagnosticData ? getStatusIcon(diagnosticData.connectionStatus) : '?'}
                  </Text>
                  <Text style={styles.statusText}>
                    {diagnosticData?.connectionStatus.toUpperCase() || 'UNKNOWN'}
                  </Text>
                </View>
                {diagnosticData?.recommendation && (
                  <Text style={styles.recommendation}>{diagnosticData.recommendation}</Text>
                )}
              </View>

              {/* Configuration */}
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Configuration</Text>
                <DiagnosticItem label="API URL" value={diagnosticData?.apiUrl || 'Unknown'} />
                <DiagnosticItem label="Timeout" value={`${diagnosticData?.timeout || 0}ms`} />
                <DiagnosticItem label="Retry Attempts" value={String(diagnosticData?.retryAttempts || 0)} />
              </View>

              {/* Network Metrics */}
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Network Metrics</Text>
                <DiagnosticItem
                  label="Quality"
                  value={diagnosticData?.networkQuality?.toUpperCase() || 'Unknown'}
                />
                <DiagnosticItem
                  label="Last Check Latency"
                  value={diagnosticData?.lastCheckLatency ? `${diagnosticData.lastCheckLatency}ms` : 'N/A'}
                />
                <DiagnosticItem
                  label="Backend Reachable"
                  value={diagnosticData?.backendReachable ? 'Yes' : 'No'}
                  valueColor={diagnosticData?.backendReachable ? '#10B981' : '#EF4444'}
                />
              </View>

              {/* Test Results */}
              {testResults.length > 0 && (
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Test Results</Text>
                  <View style={styles.testResults}>
                    {testResults.map((result, index) => (
                      <Text key={index} style={styles.testResultText}>
                        {result}
                      </Text>
                    ))}
                  </View>
                </View>
              )}

              {/* Actions */}
              <View style={styles.section}>
                <TouchableOpacity
                  style={[styles.testButton, testing && styles.disabledButton]}
                  onPress={runConnectionTest}
                  disabled={testing}
                >
                  {testing ? (
                    <View style={styles.buttonContent}>
                      <ActivityIndicator color="#FFFFFF" size="small" />
                      <Text style={styles.testButtonText}>Testing...</Text>
                    </View>
                  ) : (
                    <Text style={styles.testButtonText}>🔍 Run Connection Test</Text>
                  )}
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.refreshButton}
                  onPress={loadDiagnostics}
                  disabled={loading || testing}
                >
                  <Text style={styles.refreshButtonText}>🔄 Refresh Data</Text>
                </TouchableOpacity>
              </View>

              {/* Help Section */}
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Troubleshooting</Text>
                <View style={styles.helpBox}>
                  <Text style={styles.helpText}>• Ensure backend server is running</Text>
                  <Text style={styles.helpText}>• Check firewall settings</Text>
                  <Text style={styles.helpText}>• Verify correct API URL configuration</Text>
                  <Text style={styles.helpText}>• Try switching network connections</Text>
                </View>
              </View>
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

interface DiagnosticItemProps {
  label: string;
  value: string;
  valueColor?: string;
}

function DiagnosticItem({ label, value, valueColor }: DiagnosticItemProps) {
  return (
    <View style={styles.diagnosticItem}>
      <Text style={styles.diagnosticLabel}>{label}</Text>
      <Text style={[styles.diagnosticValue, valueColor && { color: valueColor }]}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
    backgroundColor: '#FFFFFF',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1F2937',
  },
  closeButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  closeButtonText: {
    color: '#2563EB',
    fontSize: 16,
    fontWeight: '500',
  },
  content: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 48,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#6B7280',
  },
  section: {
    backgroundColor: '#FFFFFF',
    marginTop: 12,
    paddingHorizontal: 24,
    paddingVertical: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
    marginBottom: 12,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusIndicator: {
    fontSize: 24,
    marginRight: 12,
  },
  statusText: {
    fontSize: 16,
    fontWeight: '500',
    color: '#1F2937',
  },
  recommendation: {
    marginTop: 8,
    fontSize: 14,
    color: '#6B7280',
    fontStyle: 'italic',
  },
  diagnosticItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  diagnosticLabel: {
    fontSize: 14,
    color: '#6B7280',
    flex: 1,
  },
  diagnosticValue: {
    fontSize: 14,
    fontWeight: '500',
    color: '#1F2937',
    flex: 1,
    textAlign: 'right',
  },
  testResults: {
    backgroundColor: '#F3F4F6',
    borderRadius: 8,
    padding: 12,
  },
  testResultText: {
    fontSize: 12,
    fontFamily: 'monospace',
    color: '#1F2937',
    marginBottom: 4,
  },
  testButton: {
    backgroundColor: '#2563EB',
    borderRadius: 8,
    paddingVertical: 16,
    alignItems: 'center',
    marginBottom: 12,
  },
  refreshButton: {
    borderWidth: 1,
    borderColor: '#2563EB',
    borderRadius: 8,
    paddingVertical: 16,
    alignItems: 'center',
  },
  disabledButton: {
    opacity: 0.6,
  },
  buttonContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  testButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
  refreshButtonText: {
    color: '#2563EB',
    fontSize: 16,
    fontWeight: '600',
  },
  helpBox: {
    backgroundColor: '#FEF3C7',
    borderRadius: 8,
    padding: 12,
  },
  helpText: {
    fontSize: 13,
    color: '#92400E',
    marginBottom: 4,
  },
});

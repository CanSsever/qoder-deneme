import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StackScreenProps } from '@react-navigation/stack';
import { RootStackParamList } from '../types/navigation';
import { oneShotClient } from '../utils/client';
import NetworkDiagnosticsModal from '../components/NetworkDiagnosticsModal';
import { ConnectionStatus } from 'oneshot-sdk';

type Props = StackScreenProps<RootStackParamList, 'Login'>;

export default function LoginScreen({ navigation }: Props) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('');
  const [retryCount, setRetryCount] = useState(0);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>(ConnectionStatus.UNKNOWN);
  const [checkingConnection, setCheckingConnection] = useState(false);

  useEffect(() => {
    // Perform initial connection check when screen mounts
    performPreflightCheck();
  }, []);

  const performPreflightCheck = async () => {
    setCheckingConnection(true);
    try {
      const result = await oneShotClient.quickPreflightCheck();
      setConnectionStatus(result.status);
    } catch (error) {
      console.error('Pre-flight check failed:', error);
      setConnectionStatus(ConnectionStatus.DISCONNECTED);
    } finally {
      setCheckingConnection(false);
    }
  };

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      Alert.alert('Error', 'Please enter both email and password');
      return;
    }

    setLoading(true);
    setLoadingStatus('Connecting to server...');
    setRetryCount(0);
    
    try {
      const response = await oneShotClient.login(email.trim(), password, {
        onProgress: (message) => {
          setLoadingStatus(message);
        },
        maxAttempts: 10,
        skipPreflight: false // Enable pre-flight check
      });
      
      setLoadingStatus('Login successful!');
      
      Alert.alert(
        'Success',
        `Welcome back! You have ${response.user.credits} credits.`,
        [
          {
            text: 'Continue',
            onPress: () => navigation.replace('Upload'),
          },
        ]
      );
    } catch (error: any) {
      console.error('Login error:', error);
      
      let title = 'Login Failed';
      let message = 'Login failed. Please try again.';
      let actions: any[] = [
        { text: 'OK', style: 'default' }
      ];
      
      // Enhanced error handling with specific guidance
      if (error.message.includes('not reachable') || error.message.includes('Unable to reach server')) {
        title = 'Connection Problem';
        message = error.message || 'Cannot connect to the server. Please check your internet connection.';
        actions = [
          {
            text: 'Network Diagnostics',
            onPress: () => setShowDiagnostics(true)
          },
          {
            text: 'Retry',
            onPress: () => handleLogin()
          },
          { text: 'Cancel', style: 'cancel' }
        ];
      } else if (error.message.includes('timeout')) {
        title = 'Connection Timeout';
        message = 'The server is taking too long to respond. This might be a network issue.';
        actions = [
          {
            text: 'Network Diagnostics',
            onPress: () => setShowDiagnostics(true)
          },
          {
            text: 'Retry',
            onPress: () => handleLogin()
          },
          { text: 'Cancel', style: 'cancel' }
        ];
      } else if (error.message.includes('Invalid email or password')) {
        message = 'Invalid email or password. Please check your credentials and try again.';
      } else if (error.message) {
        message = error.message;
      }
      
      Alert.alert(title, message, actions);
    } finally {
      setLoading(false);
      setLoadingStatus('');
      // Refresh connection status after login attempt
      performPreflightCheck();
    }
  };

  const testConnectivity = async () => {
    setCheckingConnection(true);
    setLoadingStatus('Testing connection...');
    
    try {
      const result = await oneShotClient.preflightCheck({
        timeout: 5000,
        retryOnFailure: true
      });
      
      setConnectionStatus(result.status);
      
      if (result.backendReachable) {
        Alert.alert(
          'Connection Test Successful',
          `Server is reachable. Response time: ${result.latency}ms\n\n${result.recommendation}`,
          [
            {
              text: 'Try Login Again',
              onPress: () => handleLogin()
            },
            { text: 'OK' }
          ]
        );
      } else {
        Alert.alert(
          'Connection Test Failed',
          `Could not reach server: ${result.error}\n\n${result.recommendation}`,
          [
            {
              text: 'Show Diagnostics',
              onPress: () => setShowDiagnostics(true)
            },
            { text: 'OK' }
          ]
        );
      }
    } catch (error: any) {
      setConnectionStatus(ConnectionStatus.DISCONNECTED);
      Alert.alert(
        'Connection Test Error',
        error.message || 'Failed to test connection'
      );
    } finally {
      setCheckingConnection(false);
      setLoadingStatus('');
    }
  };

  const getConnectionStatusDisplay = () => {
    if (checkingConnection) {
      return {
        icon: '◌',
        text: 'Checking connection...',
        color: '#3B82F6'
      };
    }

    switch (connectionStatus) {
      case ConnectionStatus.CONNECTED:
        return {
          icon: '●',
          text: 'Connected to server',
          color: '#10B981'
        };
      case ConnectionStatus.DEGRADED:
        return {
          icon: '◐',
          text: 'Connection is slow',
          color: '#F59E0B'
        };
      case ConnectionStatus.DISCONNECTED:
        return {
          icon: '○',
          text: 'Server not reachable',
          color: '#EF4444'
        };
      default:
        return {
          icon: '?',
          text: 'Connection status unknown',
          color: '#6B7280'
        };
    }
  };

  const handleDemoLogin = () => {
    Alert.alert(
      'Demo Mode',
      'This will use demo mode without authentication. Some features may not work.',
      [
        {
          text: 'Cancel',
          style: 'cancel',
        },
        {
          text: 'Continue',
          onPress: () => navigation.replace('Upload'),
        },
      ]
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardContainer}
      >
        <View style={styles.content}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.title}>OneShot</Text>
            <Text style={styles.subtitle}>AI Face Swapper</Text>
            
            {/* Connection Status Indicator */}
            <View style={styles.connectionStatus}>
              <Text style={[styles.statusIcon, { color: getConnectionStatusDisplay().color }]}>
                {getConnectionStatusDisplay().icon}
              </Text>
              <Text style={[styles.statusText, { color: getConnectionStatusDisplay().color }]}>
                {getConnectionStatusDisplay().text}
              </Text>
            </View>
          </View>

          {/* Login Form */}
          <View style={styles.form}>
            <TextInput
              style={styles.input}
              placeholder="Email"
              placeholderTextColor="#9CA3AF"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              keyboardType="email-address"
              autoCorrect={false}
              editable={!loading}
            />

            <TextInput
              style={styles.input}
              placeholder="Password"
              placeholderTextColor="#9CA3AF"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              editable={!loading}
            />

            <TouchableOpacity
              style={[styles.loginButton, loading && styles.disabledButton]}
              onPress={handleLogin}
              disabled={loading}
            >
              {loading ? (
                <View style={styles.loadingContainer}>
                  <ActivityIndicator color="#FFFFFF" size="small" />
                  <Text style={styles.loadingText}>
                    {loadingStatus || 'Logging in...'}
                  </Text>
                </View>
              ) : (
                <Text style={styles.loginButtonText}>Login</Text>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.demoButton}
              onPress={handleDemoLogin}
              disabled={loading}
            >
              <Text style={styles.demoButtonText}>Demo Mode</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.diagnosticsButton}
              onPress={() => setShowDiagnostics(true)}
              disabled={loading}
            >
              <Text style={styles.diagnosticsButtonText}>Network Diagnostics</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.testButton}
              onPress={testConnectivity}
              disabled={loading || checkingConnection}
            >
              <Text style={styles.testButtonText}>Test Connection</Text>
            </TouchableOpacity>
          </View>

          {/* Footer */}
          <View style={styles.footer}>
            <Text style={styles.footerText}>
              Don't have an account?
            </Text>
            <TouchableOpacity
              style={styles.registerLinkButton}
              onPress={() => navigation.navigate('Register')}
              disabled={loading}
            >
              <Text style={styles.registerLinkText}>Register</Text>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>

      {/* Network Diagnostics Modal */}
      <NetworkDiagnosticsModal
        visible={showDiagnostics}
        onClose={() => setShowDiagnostics(false)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  keyboardContainer: {
    flex: 1,
  },
  content: {
    flex: 1,
    paddingHorizontal: 24,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
    marginBottom: 48,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#1F2937',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#6B7280',
    marginBottom: 16,
  },
  connectionStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
    marginTop: 12,
  },
  statusIcon: {
    fontSize: 16,
    marginRight: 8,
  },
  statusText: {
    fontSize: 13,
    fontWeight: '500',
  },
  form: {
    marginBottom: 32,
  },
  input: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D1D5DB',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 16,
    marginBottom: 16,
    color: '#1F2937',
  },
  loginButton: {
    backgroundColor: '#2563EB',
    borderRadius: 8,
    paddingVertical: 16,
    alignItems: 'center',
    marginBottom: 12,
  },
  disabledButton: {
    opacity: 0.6,
  },
  loginButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  loadingText: {
    color: '#FFFFFF',
    fontSize: 14,
    marginLeft: 8,
  },
  demoButton: {
    borderWidth: 1,
    borderColor: '#2563EB',
    borderRadius: 8,
    paddingVertical: 16,
    alignItems: 'center',
  },
  demoButtonText: {
    color: '#2563EB',
    fontSize: 16,
    fontWeight: '600',
  },
  diagnosticsButton: {
    borderWidth: 1,
    borderColor: '#6B7280',
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  diagnosticsButtonText: {
    color: '#6B7280',
    fontSize: 14,
    fontWeight: '500',
  },
  testButton: {
    borderWidth: 1,
    borderColor: '#2563EB',
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  testButtonText: {
    color: '#2563EB',
    fontSize: 14,
    fontWeight: '500',
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  footerText: {
    fontSize: 14,
    color: '#6B7280',
    marginRight: 4,
  },
  registerLinkButton: {
    paddingVertical: 4,
    paddingHorizontal: 4,
  },
  registerLinkText: {
    fontSize: 14,
    color: '#2563EB',
    fontWeight: '600',
  },
});
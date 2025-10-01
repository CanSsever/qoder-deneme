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
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StackScreenProps } from '@react-navigation/stack';
import { RootStackParamList } from '../types/navigation';
import { oneShotClient } from '../utils/client';
import NetworkDiagnostics from '../utils/networkDiagnostics';

type Props = StackScreenProps<RootStackParamList, 'Login'>;

export default function LoginScreen({ navigation }: Props) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('');
  const [retryCount, setRetryCount] = useState(0);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [networkInfo, setNetworkInfo] = useState<any>(null);

  useEffect(() => {
    // Get network information on component mount
    setNetworkInfo(NetworkDiagnostics.getNetworkInfo());
  }, []);

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      Alert.alert('Error', 'Please enter both email and password');
      return;
    }

    setLoading(true);
    setLoadingStatus('Connecting to server...');
    setRetryCount(0);
    
    try {
      const response = await oneShotClient.login(email.trim(), password);
      
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
      if (error.message.includes('Unable to reach server')) {
        title = 'Connection Problem';
        message = 'Cannot connect to the server. Please check your internet connection.';
        actions = [
          {
            text: 'Network Info',
            onPress: () => setShowDiagnostics(true)
          },
          {
            text: 'Retry',
            onPress: () => handleLogin()
          },
          { text: 'Demo Mode', onPress: handleDemoLogin },
          { text: 'Cancel', style: 'cancel' }
        ];
      } else if (error.message.includes('timeout')) {
        title = 'Connection Timeout';
        message = 'The server is taking too long to respond. This might be a network issue.';
        actions = [
          {
            text: 'Retry',
            onPress: () => handleLogin()
          },
          { text: 'Demo Mode', onPress: handleDemoLogin },
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
    }
  };

  const testConnectivity = async () => {
    setLoadingStatus('Testing connection...');
    
    const result = await NetworkDiagnostics.testConnectivity();
    
    if (result.success) {
      Alert.alert(
        'Connection Test Successful',
        `Server is reachable. Response time: ${result.latency}ms`,
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
        `Could not reach server: ${result.error}`,
        [
          {
            text: 'Show Diagnostics',
            onPress: () => setShowDiagnostics(true)
          },
          { text: 'OK' }
        ]
      );
    }
    
    setLoadingStatus('');
  };

  const handleDemoLogin = () => {
    // For demo purposes - bypass login
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
              onPress={testConnectivity}
              disabled={loading}
            >
              <Text style={styles.diagnosticsButtonText}>Test Connection</Text>
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
      <Modal
        visible={showDiagnostics}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Network Diagnostics</Text>
            <TouchableOpacity
              style={styles.closeButton}
              onPress={() => setShowDiagnostics(false)}
            >
              <Text style={styles.closeButtonText}>Close</Text>
            </TouchableOpacity>
          </View>
          
          <View style={styles.modalContent}>
            <View style={styles.diagnosticItem}>
              <Text style={styles.diagnosticLabel}>API URL:</Text>
              <Text style={styles.diagnosticValue}>{networkInfo?.apiUrl}</Text>
            </View>
            
            <View style={styles.diagnosticItem}>
              <Text style={styles.diagnosticLabel}>Timeout:</Text>
              <Text style={styles.diagnosticValue}>{networkInfo?.timeout}ms</Text>
            </View>
            
            <View style={styles.diagnosticItem}>
              <Text style={styles.diagnosticLabel}>Retry Attempts:</Text>
              <Text style={styles.diagnosticValue}>{networkInfo?.retryAttempts}</Text>
            </View>
            
            <View style={styles.diagnosticItem}>
              <Text style={styles.diagnosticLabel}>Online Status:</Text>
              <Text style={[styles.diagnosticValue, networkInfo?.online ? styles.online : styles.offline]}>
                {networkInfo?.online ? 'Online' : 'Offline'}
              </Text>
            </View>
            
            <TouchableOpacity
              style={styles.testButton}
              onPress={testConnectivity}
            >
              <Text style={styles.testButtonText}>Run Connection Test</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </Modal>
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
  // Modal styles
  modalContainer: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  modalTitle: {
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
  modalContent: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 24,
  },
  diagnosticItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  diagnosticLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#6B7280',
    flex: 1,
  },
  diagnosticValue: {
    fontSize: 14,
    color: '#1F2937',
    flex: 2,
    textAlign: 'right',
  },
  online: {
    color: '#10B981',
  },
  offline: {
    color: '#EF4444',
  },
  testButton: {
    backgroundColor: '#2563EB',
    borderRadius: 8,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 32,
  },
  testButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
});
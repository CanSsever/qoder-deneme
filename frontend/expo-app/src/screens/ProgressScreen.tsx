import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Alert,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StackScreenProps } from '@react-navigation/stack';
import { RootStackParamList } from '../types/navigation';
import { oneShotClient, CONFIG } from '../utils/client';
import { JobStatusResponse } from 'oneshot-sdk';

type Props = StackScreenProps<RootStackParamList, 'Progress'>;

export default function ProgressScreen({ route, navigation }: Props) {
  const { jobId, jobType } = route.params;
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(true);

  useEffect(() => {
    let pollInterval: NodeJS.Timeout;

    const pollJobStatus = async () => {
      try {
        const jobStatus = await oneShotClient.getJob(jobId);
        setJob(jobStatus);

        if (jobStatus.status === 'succeeded') {
          setPolling(false);
          // Auto-navigate to result after a short delay
          setTimeout(() => {
            navigation.replace('Result', { job: jobStatus });
          }, 1000);
        } else if (jobStatus.status === 'failed' || jobStatus.status === 'cancelled') {
          setPolling(false);
          Alert.alert(
            'Job Failed',
            jobStatus.error_message || 'The job could not be completed.',
            [
              {
                text: 'Try Again',
                onPress: () => navigation.goBack(),
              },
              {
                text: 'Home',
                onPress: () => navigation.navigate('Upload'),
              },
            ]
          );
        }
      } catch (error: any) {
        console.error('Polling error:', error);
        setPolling(false);
        Alert.alert(
          'Error',
          'Unable to check job status. Please try again.',
          [
            {
              text: 'Retry',
              onPress: () => setPolling(true),
            },
            {
              text: 'Home',
              onPress: () => navigation.navigate('Upload'),
            },
          ]
        );
      } finally {
        setLoading(false);
      }
    };

    if (polling) {
      // Initial fetch
      pollJobStatus();
      
      // Set up polling interval
      pollInterval = setInterval(pollJobStatus, CONFIG.POLLING_INTERVAL);
    }

    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [jobId, polling, navigation]);

  const getStatusText = () => {
    if (!job) return 'Initializing...';
    
    switch (job.status) {
      case 'pending':
        return 'Job queued for processing...';
      case 'running':
        return 'Processing your image...';
      case 'succeeded':
        return 'Processing complete!';
      case 'failed':
        return 'Processing failed';
      case 'cancelled':
        return 'Job cancelled';
      default:
        return `Status: ${job.status}`;
    }
  };

  const getStatusColor = () => {
    if (!job) return '#6B7280';
    
    switch (job.status) {
      case 'pending':
        return '#F59E0B';
      case 'running':
        return '#2563EB';
      case 'succeeded':
        return '#059669';
      case 'failed':
      case 'cancelled':
        return '#DC2626';
      default:
        return '#6B7280';
    }
  };

  const formatJobType = (type: string) => {
    switch (type) {
      case 'face_restore':
        return 'Face Restoration';
      case 'face_swap':
        return 'Face Swap';
      case 'upscale':
        return 'Image Upscale';
      default:
        return type;
    }
  };

  const handleCancel = () => {
    Alert.alert(
      'Cancel Job',
      'Are you sure you want to cancel this job? This action cannot be undone.',
      [
        {
          text: 'No',
          style: 'cancel',
        },
        {
          text: 'Yes, Cancel',
          style: 'destructive',
          onPress: () => {
            setPolling(false);
            navigation.navigate('Upload');
          },
        },
      ]
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Processing Job</Text>
          <Text style={styles.jobType}>{formatJobType(jobType)}</Text>
          <Text style={styles.jobId}>Job ID: {jobId}</Text>
        </View>

        {/* Progress Section */}
        <View style={styles.progressSection}>
          {loading ? (
            <ActivityIndicator size="large" color="#2563EB" />
          ) : (
            <>
              {/* Progress Bar */}
              <View style={styles.progressBarContainer}>
                <View 
                  style={[
                    styles.progressBar, 
                    { width: `${job?.progress || 0}%` }
                  ]} 
                />
              </View>
              
              {/* Progress Text */}
              <Text style={styles.progressText}>
                {Math.round(job?.progress || 0)}% Complete
              </Text>
            </>
          )}

          {/* Status */}
          <View style={styles.statusContainer}>
            <View style={[styles.statusDot, { backgroundColor: getStatusColor() }]} />
            <Text style={[styles.statusText, { color: getStatusColor() }]}>
              {getStatusText()}
            </Text>
          </View>

          {/* Timing Info */}
          {job && (
            <View style={styles.timingInfo}>
              <Text style={styles.timingText}>
                Started: {new Date(job.created_at).toLocaleTimeString()}
              </Text>
              {job.completed_at && (
                <Text style={styles.timingText}>
                  Completed: {new Date(job.completed_at).toLocaleTimeString()}
                </Text>
              )}
            </View>
          )}
        </View>

        {/* Actions */}
        <View style={styles.actions}>
          {polling && (
            <TouchableOpacity style={styles.cancelButton} onPress={handleCancel}>
              <Text style={styles.cancelButtonText}>Cancel Job</Text>
            </TouchableOpacity>
          )}
          
          {!polling && job?.status !== 'succeeded' && (
            <TouchableOpacity 
              style={styles.homeButton} 
              onPress={() => navigation.navigate('Upload')}
            >
              <Text style={styles.homeButtonText}>Back to Upload</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Tips */}
        <View style={styles.tips}>
          <Text style={styles.tipsTitle}>Processing Tips:</Text>
          <Text style={styles.tipText}>• Keep the app open for faster updates</Text>
          <Text style={styles.tipText}>• Processing time varies by image complexity</Text>
          <Text style={styles.tipText}>• You'll be notified when complete</Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  content: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
    marginBottom: 48,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#1F2937',
    marginBottom: 8,
  },
  jobType: {
    fontSize: 18,
    color: '#2563EB',
    fontWeight: '600',
    marginBottom: 4,
  },
  jobId: {
    fontSize: 12,
    color: '#6B7280',
    fontFamily: 'monospace',
  },
  progressSection: {
    alignItems: 'center',
    marginBottom: 48,
  },
  progressBarContainer: {
    width: '100%',
    height: 8,
    backgroundColor: '#E5E7EB',
    borderRadius: 4,
    marginBottom: 16,
    overflow: 'hidden',
  },
  progressBar: {
    height: '100%',
    backgroundColor: '#2563EB',
    borderRadius: 4,
  },
  progressText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1F2937',
    marginBottom: 16,
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 24,
  },
  statusDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 8,
  },
  statusText: {
    fontSize: 16,
    fontWeight: '500',
  },
  timingInfo: {
    alignItems: 'center',
  },
  timingText: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 4,
  },
  actions: {
    marginBottom: 32,
  },
  cancelButton: {
    borderWidth: 1,
    borderColor: '#DC2626',
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
  },
  cancelButtonText: {
    color: '#DC2626',
    fontSize: 16,
    fontWeight: '600',
  },
  homeButton: {
    backgroundColor: '#2563EB',
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
  },
  homeButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  tips: {
    backgroundColor: '#EFF6FF',
    borderRadius: 8,
    padding: 16,
  },
  tipsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
    marginBottom: 8,
  },
  tipText: {
    fontSize: 14,
    color: '#374151',
    marginBottom: 4,
  },
});
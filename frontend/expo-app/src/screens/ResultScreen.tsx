import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Image,
  TouchableOpacity,
  ScrollView,
  Alert,
  Share,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StackScreenProps } from '@react-navigation/stack';
import { RootStackParamList } from '../types/navigation';
import { oneShotClient } from '../utils/client';
import { Artifact } from 'oneshot-sdk';

type Props = StackScreenProps<RootStackParamList, 'Result'>;

export default function ResultScreen({ route, navigation }: Props) {
  const { job } = route.params;
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loadingArtifacts, setLoadingArtifacts] = useState(true);
  const [imageLoading, setImageLoading] = useState(true);

  useEffect(() => {
    loadArtifacts();
  }, []);

  const loadArtifacts = async () => {
    try {
      const artifactList = await oneShotClient.listArtifacts(job.job_id);
      setArtifacts(artifactList);
    } catch (error) {
      console.error('Failed to load artifacts:', error);
      // Fallback: create artifact from job result_url
      if (job.result_url) {
        setArtifacts([
          {
            id: `${job.job_id}_result`,
            job_id: job.job_id,
            artifact_type: 'image',
            output_url: job.result_url,
            created_at: job.completed_at || job.created_at,
          },
        ]);
      }
    } finally {
      setLoadingArtifacts(false);
    }
  };

  const handleShare = async () => {
    if (artifacts.length === 0) {
      Alert.alert('Error', 'No result to share');
      return;
    }

    try {
      await Share.share({
        message: `Check out my AI-processed image from OneShot! ${artifacts[0].output_url}`,
        url: artifacts[0].output_url,
      });
    } catch (error) {
      console.error('Share failed:', error);
    }
  };

  const handleDownload = () => {
    if (artifacts.length === 0) {
      Alert.alert('Error', 'No result to download');
      return;
    }

    Alert.alert(
      'Download',
      'To download the image, please copy the URL and open it in your browser.',
      [
        {
          text: 'Copy URL',
          onPress: () => {
            // In a real app, you'd use Clipboard API
            Alert.alert('URL', artifacts[0].output_url);
          },
        },
        {
          text: 'Cancel',
          style: 'cancel',
        },
      ]
    );
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

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'Unknown size';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  const getProcessingTime = () => {
    if (!job.completed_at) return 'Unknown';
    
    const start = new Date(job.created_at);
    const end = new Date(job.completed_at);
    const diffSeconds = Math.round((end.getTime() - start.getTime()) / 1000);
    
    if (diffSeconds < 60) {
      return `${diffSeconds} seconds`;
    } else {
      const minutes = Math.floor(diffSeconds / 60);
      const seconds = diffSeconds % 60;
      return `${minutes}m ${seconds}s`;
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        <View style={styles.content}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.title}>Processing Complete!</Text>
            <Text style={styles.subtitle}>{formatJobType(job.status)}</Text>
          </View>

          {/* Result Image */}
          <View style={styles.imageSection}>
            {loadingArtifacts ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#2563EB" />
                <Text style={styles.loadingText}>Loading result...</Text>
              </View>
            ) : artifacts.length > 0 ? (
              <View style={styles.imageContainer}>
                <Image
                  source={{ uri: artifacts[0].output_url }}
                  style={styles.resultImage}
                  onLoadStart={() => setImageLoading(true)}
                  onLoadEnd={() => setImageLoading(false)}
                  resizeMode="contain"
                />
                {imageLoading && (
                  <View style={styles.imageLoadingOverlay}>
                    <ActivityIndicator size="large" color="#2563EB" />
                  </View>
                )}
              </View>
            ) : (
              <View style={styles.noResultContainer}>
                <Text style={styles.noResultText}>No result available</Text>
              </View>
            )}
          </View>

          {/* Job Info */}
          <View style={styles.infoSection}>
            <Text style={styles.infoTitle}>Job Details</Text>
            
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Job ID:</Text>
              <Text style={styles.infoValue}>{job.job_id}</Text>
            </View>
            
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Status:</Text>
              <Text style={[styles.infoValue, styles.successText]}>
                {job.status.toUpperCase()}
              </Text>
            </View>
            
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Processing Time:</Text>
              <Text style={styles.infoValue}>{getProcessingTime()}</Text>
            </View>
            
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Progress:</Text>
              <Text style={styles.infoValue}>{job.progress}%</Text>
            </View>

            {artifacts.length > 0 && (
              <>
                <View style={styles.infoRow}>
                  <Text style={styles.infoLabel}>File Size:</Text>
                  <Text style={styles.infoValue}>
                    {formatFileSize(artifacts[0].file_size)}
                  </Text>
                </View>
                
                <View style={styles.infoRow}>
                  <Text style={styles.infoLabel}>Format:</Text>
                  <Text style={styles.infoValue}>
                    {artifacts[0].mime_type || 'image/jpeg'}
                  </Text>
                </View>
              </>
            )}
          </View>

          {/* Action Buttons */}
          {artifacts.length > 0 && (
            <View style={styles.actions}>
              <TouchableOpacity style={styles.shareButton} onPress={handleShare}>
                <Text style={styles.shareButtonText}>Share Result</Text>
              </TouchableOpacity>
              
              <TouchableOpacity style={styles.downloadButton} onPress={handleDownload}>
                <Text style={styles.downloadButtonText}>Download</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Navigation */}
          <View style={styles.navigation}>
            <TouchableOpacity
              style={styles.newJobButton}
              onPress={() => navigation.navigate('Upload')}
            >
              <Text style={styles.newJobButtonText}>Create New Job</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: 16,
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#059669',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 16,
    color: '#6B7280',
  },
  imageSection: {
    marginBottom: 24,
  },
  loadingContainer: {
    height: 300,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#6B7280',
  },
  imageContainer: {
    position: 'relative',
    borderRadius: 12,
    overflow: 'hidden',
    backgroundColor: '#FFFFFF',
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 3.84,
    elevation: 5,
  },
  resultImage: {
    width: '100%',
    height: 300,
  },
  imageLoadingOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
  },
  noResultContainer: {
    height: 300,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
  },
  noResultText: {
    fontSize: 16,
    color: '#6B7280',
  },
  infoSection: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  infoTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1F2937',
    marginBottom: 16,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  infoLabel: {
    fontSize: 14,
    color: '#6B7280',
    flex: 1,
  },
  infoValue: {
    fontSize: 14,
    color: '#1F2937',
    fontWeight: '500',
    flex: 1,
    textAlign: 'right',
  },
  successText: {
    color: '#059669',
  },
  actions: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 24,
  },
  shareButton: {
    flex: 1,
    backgroundColor: '#2563EB',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
  },
  shareButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  downloadButton: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#2563EB',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
  },
  downloadButtonText: {
    color: '#2563EB',
    fontSize: 16,
    fontWeight: '600',
  },
  navigation: {
    marginBottom: 32,
  },
  newJobButton: {
    backgroundColor: '#059669',
    borderRadius: 8,
    paddingVertical: 16,
    alignItems: 'center',
  },
  newJobButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
});
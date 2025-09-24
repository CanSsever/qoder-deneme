import React, {
  useState,
  useMemo,
  useCallback,
  useLayoutEffect,
  useEffect,
  useRef,
} from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Image,
  ScrollView,
  ActivityIndicator,
  Animated,
  Easing,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StackScreenProps } from '@react-navigation/stack';
import * as ImagePicker from 'expo-image-picker';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { RootStackParamList } from '../types/navigation';
import { oneShotClient, CONFIG } from '../utils/client';
import { JobType } from 'oneshot-sdk';

type Props = StackScreenProps<RootStackParamList, 'Upload'>;

type PickerSlot = 'source' | 'target';

interface PickerAsset {
  uri: string;
  width?: number;
  height?: number;
  fileSize?: number;
  fileName?: string;
  mimeType?: string;
}

interface JobFormState {
  source: PickerAsset | null;
  target: PickerAsset | null;
}

const INITIAL_FORM_STATE: Record<JobType, JobFormState> = {
  [JobType.FACE_RESTORATION]: { source: null, target: null },
  [JobType.FACE_SWAP]: { source: null, target: null },
  [JobType.UPSCALE]: { source: null, target: null },
};

const JOB_TABS: Array<{ type: JobType; label: string; icon: string }> = [
  { type: JobType.FACE_RESTORATION, label: 'Restore', icon: 'auto-fix' },
  { type: JobType.FACE_SWAP, label: 'Swap', icon: 'swap-horizontal' },
  { type: JobType.UPSCALE, label: 'Upscale', icon: 'arrow-expand' },
];

const heicRegex = /(\.heic$|\.heif$)/i;

const formatFileInfo = (asset?: PickerAsset | null) => {
  if (!asset) {
    return 'Choose image';
  }

  const parts: string[] = [];
  if (asset.width && asset.height) {
    parts.push(`${asset.width}×${asset.height}`);
  }
  if (asset.fileSize) {
    const sizeInMb = asset.fileSize / (1024 * 1024);
    if (sizeInMb >= 1) {
      parts.push(`${sizeInMb.toFixed(1)} MB`);
    } else {
      const sizeInKb = asset.fileSize / 1024;
      const readableKb = Math.max(Math.round(sizeInKb), 1);
      parts.push(`${readableKb} KB`);
    }
  }
  return parts.length ? parts.join(' | ') : 'Image selected';
};

const getMimeInfo = (asset: PickerAsset) => {
  if (asset.mimeType) {
    const typeParts = asset.mimeType.split('/');
    return {
      mimeType: asset.mimeType,
      extension: typeParts[1] || 'jpg',
    };
  }

  if (asset.fileName) {
    const ext = asset.fileName.split('.').pop();
    if (ext) {
      const lower = ext.toLowerCase();
      if (lower === 'png') {
        return { mimeType: 'image/png', extension: 'png' };
      }
      if (lower === 'webp') {
        return { mimeType: 'image/webp', extension: 'webp' };
      }
    }
  }

  return { mimeType: 'image/jpeg', extension: 'jpg' };
};

const SkeletonLoader = () => {
  const shimmer = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animation = Animated.loop(
      Animated.timing(shimmer, {
        toValue: 1,
        duration: 1400,
        easing: Easing.linear,
        useNativeDriver: true,
      })
    );

    animation.start();
    return () => {
      animation.stop();
    };
  }, [shimmer]);

  const translateX = shimmer.interpolate({
    inputRange: [0, 1],
    outputRange: [-150, 300],
  });

  return (
    <View style={styles.skeletonGroup}>
      {[0, 1, 2].map(index => (
        <View key={index} style={styles.skeletonRow}>
          <Animated.View
            style={[
              styles.shimmerOverlay,
              { transform: [{ translateX }] },
            ]}
          />
        </View>
      ))}
    </View>
  );
};

export default function UploadScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const [selectedJobType, setSelectedJobType] = useState<JobType>(JobType.FACE_RESTORATION);
  const [formState, setFormState] = useState<Record<JobType, JobFormState>>(INITIAL_FORM_STATE);
  const [bannerMessage, setBannerMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useLayoutEffect(() => {
    navigation.setOptions({
      title: 'Create Job',
      headerTitleAlign: 'center',
      headerStyle: {
        backgroundColor: '#1D4ED8',
        height: 64,
        shadowOpacity: 0,
        elevation: 0,
      },
      headerTintColor: '#FFFFFF',
      headerTitleStyle: {
        fontSize: 20,
        fontWeight: '600',
      },
      headerRight: () => (
        <TouchableOpacity
          style={styles.headerIconButton}
          onPress={() => setBannerMessage('History coming soon.')}
          accessibilityRole="button"
          accessibilityLabel="Open history"
        >
          <Feather name="clock" size={20} color="#FFFFFF" />
        </TouchableOpacity>
      ),
    });
  }, [navigation]);

  useEffect(() => {
    if (!bannerMessage) {
      return;
    }

    const timer = setTimeout(() => setBannerMessage(null), 4000);
    return () => clearTimeout(timer);
  }, [bannerMessage]);

  const pickerSlots = useMemo(() => {
    if (selectedJobType === JobType.FACE_SWAP) {
      return [
        { slot: 'source' as PickerSlot, label: 'Source Face' },
        { slot: 'target' as PickerSlot, label: 'Target Face' },
      ];
    }

    return [{ slot: 'source' as PickerSlot, label: 'Source Image' }];
  }, [selectedJobType]);

  const currentState = formState[selectedJobType];
  const isSwap = selectedJobType === JobType.FACE_SWAP;
  const hasAllRequiredImages = pickerSlots.every(({ slot }) => currentState[slot]);

  const showBanner = useCallback((message: string) => {
    setBannerMessage(message);
  }, []);

  const pickImage = useCallback(
    async (slot: PickerSlot) => {
      if (loading) {
        return;
      }

      try {
        const result = await ImagePicker.launchImageLibraryAsync({
          mediaTypes: ImagePicker.MediaTypeOptions.Images,
          allowsEditing: false,
          quality: 1,
        });

        if (result.canceled || !result.assets?.length) {
          return;
        }

        const asset = result.assets[0];
        const uri = asset.uri || '';
        const name = asset.fileName || '';
        const fileSize = asset.fileSize || 0;

        if (heicRegex.test(uri) || heicRegex.test(name)) {
          showBanner('HEIC not supported. Convert to JPEG.');
          return;
        }

        if (fileSize > CONFIG.MAX_FILE_SIZE) {
          const maxMb = (CONFIG.MAX_FILE_SIZE / (1024 * 1024)).toFixed(1);
          showBanner(`File too large. Max ${maxMb} MB.`);
          return;
        }

        const nextAsset: PickerAsset = {
          uri,
          width: asset.width,
          height: asset.height,
          fileSize,
          fileName: name,
          mimeType: asset.mimeType,
        };

        setFormState(prev => ({
          ...prev,
          [selectedJobType]: {
            ...prev[selectedJobType],
            [slot]: nextAsset,
          },
        }));
        setBannerMessage(null);
      } catch (error) {
        console.error('Image picker error:', error);
        showBanner('Unable to select image. Please try again.');
      }
    },
    [loading, selectedJobType, showBanner]
  );

  const handleCreateJob = useCallback(async () => {
    const activeState = formState[selectedJobType];
    const sourceAsset = activeState.source;
    const targetAsset = activeState.target;

    if (!sourceAsset || (isSwap && !targetAsset)) {
      showBanner('Please select the required images.');
      return;
    }

    setLoading(true);

    try {
      const sourceBlob = await fetch(sourceAsset.uri).then(res => res.blob());
      const { mimeType: sourceMime, extension: sourceExt } = getMimeInfo(sourceAsset);
      const inputPresign = await oneShotClient.presignUpload(
        `input_${Date.now()}.${sourceExt}`,
        sourceMime,
        sourceBlob.size
      );
      await oneShotClient.uploadFile(inputPresign.presigned_url, sourceBlob, sourceMime);
      const inputUrl = inputPresign.presigned_url.split('?')[0];

      let targetUrl: string | undefined;
      if (isSwap && targetAsset) {
        const targetBlob = await fetch(targetAsset.uri).then(res => res.blob());
        const { mimeType: targetMime, extension: targetExt } = getMimeInfo(targetAsset);
        const targetPresign = await oneShotClient.presignUpload(
          `target_${Date.now()}.${targetExt}`,
          targetMime,
          targetBlob.size
        );
        await oneShotClient.uploadFile(targetPresign.presigned_url, targetBlob, targetMime);
        targetUrl = targetPresign.presigned_url.split('?')[0];
      }

      const jobParams: Record<string, any> = {};

      switch (selectedJobType) {
        case JobType.FACE_RESTORATION:
          jobParams.face_restore = 'gfpgan';
          jobParams.enhance = true;
          break;
        case JobType.FACE_SWAP:
          jobParams.blend = 0.8;
          break;
        case JobType.UPSCALE:
          jobParams.scale_factor = 2;
          jobParams.model = 'realesrgan_x4plus';
          break;
      }

      const jobResponse = await oneShotClient.createJob(
        selectedJobType,
        inputUrl,
        jobParams,
        targetUrl
      );

      navigation.navigate('Progress', {
        jobId: jobResponse.job_id,
        jobType: selectedJobType,
      });
    } catch (error: any) {
      console.error('Upload error:', error);

      let message = 'Upload failed. Please try again.';
      if (typeof error?.message === 'string') {
        if (error.message.includes('Rate limit')) {
          message = 'Rate limit exceeded. Please wait before creating another job.';
        } else if (error.message.includes('Payment required')) {
          message = 'Payment required. Please upgrade your plan.';
        } else if (error.message.includes('Validation')) {
          message = 'Invalid image or parameters. Please check your inputs.';
        }
      }

      showBanner(message);
    } finally {
      setLoading(false);
    }
  }, [formState, isSwap, navigation, selectedJobType, showBanner]);

  const renderPickerRow = useCallback(
    ({ slot, label }: { slot: PickerSlot; label: string }) => {
      const asset = currentState[slot];
      const info = formatFileInfo(asset);

      return (
        <TouchableOpacity
          key={slot}
          style={[styles.pickerRow, loading && styles.pickerRowDisabled]}
          onPress={() => pickImage(slot)}
          disabled={loading}
        >
          <View style={styles.thumbnailWrapper}>
            {asset ? (
              <Image source={{ uri: asset.uri }} style={styles.thumbnailImage} />
            ) : (
              <View style={styles.thumbnailPlaceholder}>
                <Feather name="image" size={20} color="#94A3B8" />
              </View>
            )}
          </View>
          <View style={styles.pickerTextGroup}>
            <Text style={styles.pickerLabel}>{label}</Text>
            <Text style={[styles.pickerSubtitle, asset && styles.pickerSubtitleActive]}>
              {info}
            </Text>
          </View>
          <Feather name="chevron-right" size={20} color="#64748B" />
        </TouchableOpacity>
      );
    },
    [currentState, loading, pickImage]
  );

  const shouldShowEmptyState = !currentState.source && (!isSwap || !currentState.target);

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.screen}>
        {bannerMessage && (
          <View style={styles.banner}>
            <Feather name="alert-circle" size={18} color="#DC2626" />
            <Text style={styles.bannerText}>{bannerMessage}</Text>
            <TouchableOpacity
              onPress={() => setBannerMessage(null)}
              accessibilityRole="button"
              accessibilityLabel="Dismiss message"
            >
              <Feather name="x" size={16} color="#DC2626" />
            </TouchableOpacity>
          </View>
        )}

        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.screenTitle}>Choose a task</Text>

          <View style={styles.segmentedContainer}>
            {JOB_TABS.map(({ type, label, icon }) => {
              const isActive = selectedJobType === type;
              return (
                <TouchableOpacity
                  key={type}
                  style={[styles.tabButton, isActive && styles.tabButtonActive]}
                  onPress={() => {
                    setSelectedJobType(type);
                    setBannerMessage(null);
                  }}
                  disabled={loading}
                >
                  <MaterialCommunityIcons
                    name={icon as any}
                    size={18}
                    color={isActive ? '#FFFFFF' : '#1D4ED8'}
                    style={styles.tabIcon}
                  />
                  <Text style={[styles.tabLabel, isActive && styles.tabLabelActive]}>{label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <View style={styles.formSection}>
            {loading ? (
              <SkeletonLoader />
            ) : (
              <>
                {shouldShowEmptyState && (
                  <View style={styles.emptyState}>
                    <MaterialCommunityIcons
                      name="image-search-outline"
                      size={48}
                      color="#A1A1AA"
                    />
                    <Text style={styles.emptyTitle}>No images selected</Text>
                    <Text style={styles.emptySubtitle}>
                      Add the required images to continue with your job.
                    </Text>
                  </View>
                )}
                <View style={styles.pickersGroup}>
                  {pickerSlots.map(renderPickerRow)}
                </View>
              </>
            )}
          </View>
        </ScrollView>

        <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 16) }]}>
          <TouchableOpacity
            style={[styles.primaryButton, (!hasAllRequiredImages || loading) && styles.primaryButtonDisabled]}
            onPress={handleCreateJob}
            disabled={!hasAllRequiredImages || loading}
          >
            {loading ? (
              <ActivityIndicator color="#FFFFFF" />
            ) : (
              <Text style={styles.primaryButtonText}>Continue</Text>
            )}
          </TouchableOpacity>
          <Text style={styles.helperText}>Est. time: 10-20s | 1 credit</Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  screen: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingBottom: 160,
  },
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginHorizontal: 16,
    marginTop: 16,
    marginBottom: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#FEE2E2',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#FCA5A5',
    gap: 12,
  },
  bannerText: {
    flex: 1,
    fontSize: 14,
    color: '#B91C1C',
  },
  screenTitle: {
    marginTop: 16,
    marginBottom: 16,
    fontSize: 22,
    fontWeight: '600',
    color: '#0F172A',
  },
  segmentedContainer: {
    flexDirection: 'row',
    gap: 12,
  },
  tabButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderWidth: 1,
    borderRadius: 12,
    borderColor: '#94A3B8',
    backgroundColor: '#FFFFFF',
  },
  tabButtonActive: {
    backgroundColor: '#1D4ED8',
    borderColor: '#1D4ED8',
  },
  tabIcon: {
    marginRight: 6,
  },
  tabLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: '#1D4ED8',
  },
  tabLabelActive: {
    color: '#FFFFFF',
  },
  formSection: {
    marginTop: 24,
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 24,
    paddingHorizontal: 16,
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 16,
  },
  emptyTitle: {
    marginTop: 12,
    fontSize: 18,
    fontWeight: '600',
    color: '#1F2937',
  },
  emptySubtitle: {
    marginTop: 8,
    textAlign: 'center',
    fontSize: 15,
    color: '#6B7280',
  },
  pickersGroup: {
    gap: 12,
  },
  pickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    gap: 12,
  },
  pickerRowDisabled: {
    opacity: 0.6,
  },
  thumbnailWrapper: {
    width: 48,
    height: 48,
    borderRadius: 12,
    overflow: 'hidden',
    backgroundColor: '#F1F5F9',
    alignItems: 'center',
    justifyContent: 'center',
  },
  thumbnailImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  thumbnailPlaceholder: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pickerTextGroup: {
    flex: 1,
  },
  pickerLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#0F172A',
    marginBottom: 4,
  },
  pickerSubtitle: {
    fontSize: 15,
    color: '#94A3B8',
  },
  pickerSubtitleActive: {
    color: '#1E293B',
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: '#E2E8F0',
    paddingHorizontal: 16,
    paddingTop: 16,
    backgroundColor: '#FFFFFF',
  },
  primaryButton: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 12,
    backgroundColor: '#2563EB',
  },
  primaryButtonDisabled: {
    backgroundColor: '#93C5FD',
  },
  primaryButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  helperText: {
    marginTop: 8,
    textAlign: 'center',
    fontSize: 15,
    color: '#64748B',
  },
  skeletonGroup: {
    gap: 12,
  },
  skeletonRow: {
    height: 72,
    borderRadius: 12,
    backgroundColor: '#E2E8F0',
    overflow: 'hidden',
  },
  shimmerOverlay: {
    position: 'absolute',
    height: '100%',
    width: '45%',
    backgroundColor: 'rgba(255,255,255,0.7)',
    opacity: 0.8,
  },
  headerIconButton: {
    marginRight: 12,
    padding: 6,
  },
});




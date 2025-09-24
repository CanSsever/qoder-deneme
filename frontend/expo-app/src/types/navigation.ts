/**
 * Navigation types
 */
import { JobStatusResponse } from 'oneshot-sdk';

export type RootStackParamList = {
  Login: undefined;
  Register: undefined;
  Upload: undefined;
  Progress: { 
    jobId: string;
    jobType: string;
  };
  Result: { 
    job: JobStatusResponse;
  };
};

export type NavigationProp = {
  navigate: (screen: keyof RootStackParamList, params?: any) => void;
  goBack: () => void;
  replace: (screen: keyof RootStackParamList, params?: any) => void;
};
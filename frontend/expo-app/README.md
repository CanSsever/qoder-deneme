# OneShot Expo Sample App

A complete mobile app example demonstrating integration with the OneShot Face Swapper API using the OneShot SDK.

## Features

- [AUTH] Login and registration with demo mode
- [CAMERA] Camera and gallery integration
- [PALETTE] Face restoration, swap, and upscale job types
- [TIMER] Live job status updates
- [RESULTS] Processed image viewer with sharing
- [MOBILE] Optimised for iOS and Android

## Quick Start

### Prerequisites

- Node.js 16+
- Expo CLI: `npm install -g @expo/cli`
- OneShot backend running (see main README)

### Installation

1. **Install dependencies:**
   ```bash
   cd frontend/expo-app
   npm install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Only update values if you need custom overrides
   ```

3. **Start the app:**
   ```bash
   npm start
   # or
   expo start
   ```

4. **Run on device:**
   - Scan QR code with Expo Go app
   - Or press `i` for iOS simulator
   - Or press `a` for Android emulator

## Environment Configuration

Create a `.env` file (copied from `.env.example`) to override detected values when needed:

```env
# Optional: override automatically detected API endpoint
EXPO_PUBLIC_API_URL=
EXPO_PUBLIC_API_PORT=8000
EXPO_PUBLIC_API_TIMEOUT=30000
```

> ℹ️ The Expo config now autodetects your current LAN IP. Only set `EXPO_PUBLIC_API_URL`
> when you need a custom domain (for example, an ngrok/cloudflared tunnel or staging backend).

## App Structure

```
src/
|--- screens/           # Main app screens
|   |--- LoginScreen.tsx
|   |--- RegisterScreen.tsx
|   |--- UploadScreen.tsx  
|   |--- ProgressScreen.tsx
|   `--- ResultScreen.tsx
|--- components/        # Reusable components
|--- types/            # TypeScript definitions
|   `--- navigation.ts
`--- utils/            # Utilities and configuration
    `--- client.ts     # SDK client setup
```

## Usage Guide

### 1. Authentication Flow

The app starts with a login screen that supports:

- **Email/Password Login** - Authenticate with the backend
- **New User Registration** - Create account with email and password
- **Demo Mode** - Skip authentication for testing (limited functionality)

#### Login Implementation
```typescript
// Login existing user
import { oneShotClient } from '../utils/client';

const handleLogin = async () => {
  try {
    const response = await oneShotClient.login(email, password);
    // Navigate to upload screen
  } catch (error) {
    // Handle authentication errors
  }
};
```

#### Registration Implementation
```typescript
// Register new user
const handleRegister = async () => {
  try {
    const response = await oneShotClient.register(email, password);
    // User is automatically logged in after registration
    // Navigate to upload screen
  } catch (error) {
    // Handle registration errors (duplicate email, weak password, etc.)
  }
};
```

#### Registration Features
- **Email Validation** - Ensures valid email format
- **Password Requirements** - Minimum 8 characters
- **Password Confirmation** - Prevents typos
- **Error Handling** - Specific messages for duplicate emails, validation errors
- **Auto-Login** - Automatically logs in user after successful registration
- **UI Consistency** - Same design patterns as login screen
```

### 2. Upload Screen

Select job type and upload images:

- **Face Restoration** - Enhance face quality (requires 1 image)
- **Face Swap** - Replace faces (requires 2 images)
- **Image Upscaling** - Increase resolution (requires 1 image)

```typescript
// Job creation example
const job = await oneShotClient.createJob(
  JobType.FACE_RESTORATION,
  inputImageUrl,
  { face_restore: 'gfpgan', enhance: true }
);
```

### 3. Progress Screen

Real-time job monitoring with:

- **Progress Bar** - Visual progress indicator
- **Status Updates** - Current processing stage
- **Polling** - Automatic status refresh every 2 seconds
- **Error Handling** - Graceful failure handling

```typescript
// Progress polling
useEffect(() => {
  const pollJob = async () => {
    const status = await oneShotClient.getJob(jobId);
    if (status.status === 'succeeded') {
      // Navigate to results
    }
  };
  
  const interval = setInterval(pollJob, 2000);
  return () => clearInterval(interval);
}, []);
```

### 4. Result Screen

Display and interact with results:

- **Image Preview** - High-quality result display
- **Job Details** - Processing time, file size, etc.
- **Share/Download** - Export processed images
- **New Job** - Quick access to create another job

## SDK Integration

The app demonstrates key SDK features:

### Authentication
```typescript
// Login with credentials
await client.login(email, password);

// Register new user
await client.register(email, password);

// Or use API key
const client = new OneShotClient({
  baseUrl: CONFIG.API_URL,
  apiKey: 'your-api-key'
});
```

### File Upload
```typescript
// Generate presigned URL
const presign = await client.presignUpload(filename, contentType, fileSize);

// Upload file
await client.uploadFile(presign.presigned_url, blob, contentType);
```

### Job Processing
```typescript
// Create job
const job = await client.createJob(jobType, inputUrl, params, targetUrl);

// Monitor progress
const result = await client.waitForJob(job.job_id, {
  onProgress: (job) => setProgress(job.progress)
});
```

### Error Handling
```typescript
try {
  await client.createJob(jobType, inputUrl);
} catch (error) {
  if (error instanceof RateLimitError) {
    showAlert('Rate limit exceeded');
  } else if (error instanceof PaymentRequiredError) {
    showAlert('Upgrade required');
  }
}
```

## Customization

### Styling

The app uses a consistent design system with:

- **Colors**: Blue primary (#2563EB), success green (#059669)
- **Typography**: Native system fonts with proper hierarchy
- **Layout**: Safe area handling, responsive design
- **Components**: Reusable styled components

### Navigation

Stack navigation with type-safe routing:

```typescript
type RootStackParamList = {
  Login: undefined;
  Register: undefined;
  Upload: undefined;
  Progress: { jobId: string; jobType: string };
  Result: { job: JobStatusResponse };
};
```

### Configuration

Customize app behavior via `src/utils/client.ts`:

```typescript
export const CONFIG = {
  API_URL: getApiUrl(),
  POLLING_INTERVAL: 2000,        // Progress polling frequency
  MAX_FILE_SIZE: 20 * 1024 * 1024, // 20MB limit
  ALLOWED_IMAGE_TYPES: ['image/jpeg', 'image/png', 'image/webp']
};
```

## Development

### Scripts

```bash
# Start development server
npm start

# Run on iOS
npm run ios

# Run on Android  
npm run android

# Run on web
npm run web

# Type check
npx tsc --noEmit
```

### Adding New Features

1. **New Screen:**
   ```bash
   # Add to src/screens/NewScreen.tsx
   # Update navigation types
   # Add to App.tsx navigator
   ```

2. **New Job Type:**
   ```typescript
   // Add to JobType enum in SDK
   // Update job options in UploadScreen
   // Handle in job creation logic
   ```

3. **Custom Components:**
   ```bash
   # Add to src/components/
   # Export from index file
   # Use throughout app
   ```

## Testing

### Manual Testing

1. **Authentication Flow:**
   - Test valid/invalid login credentials
   - Test new user registration
   - Test email validation and password requirements
   - Test duplicate email registration
   - Test demo mode
   - Verify token persistence

2. **Upload Flow:**
   - Test different image formats
   - Test file size limits
   - Test network errors

3. **Job Processing:**
   - Test all job types
   - Test progress updates
   - Test error scenarios

4. **Result Display:**
   - Test image loading
   - Test share functionality
   - Test navigation flows

### Automated Testing

```bash
# Add Jest/React Native Testing Library
npm install --save-dev jest @testing-library/react-native

# Run tests
npm test
```

## Deployment

### Production Build

```bash
# Build for production
expo build:ios
expo build:android

# Or with EAS Build
eas build --platform all
```

### Environment Variables

Production configuration:

```env
EXPO_PUBLIC_API_URL=https://api.oneshot.com
EXPO_PUBLIC_API_TIMEOUT=30000
```

## Troubleshooting

### Common Issues

1. **Network Errors:**
   - Check `EXPO_PUBLIC_API_URL` in `.env` (or let auto-detect handle it)
   - Verify backend is running
   - Check device network connectivity

2. **Image Upload Fails:**
   - Verify file size < 20MB
   - Check image format (JPEG/PNG/WebP)
   - Ensure valid presigned URL

3. **Job Stuck in Pending:**
   - Check backend worker is running
   - Verify Redis connection
   - Check job queue status

4. **Authentication Errors:**
   - Verify credentials
   - Check JWT token expiry
   - Ensure backend auth service is running

### Debug Mode

Enable debug logging:

```typescript
// In client.ts
const client = new OneShotClient({
  baseUrl: CONFIG.API_URL,
  // Add debug flag when available
});

// Add console.log statements
console.log('Job created:', jobResponse);
```

## Performance

### Optimization Tips

- **Image Compression**: Reduce image quality for faster uploads
- **Polling Frequency**: Adjust based on expected job duration
- **Memory Management**: Clear large image references after upload
- **Network Efficiency**: Use appropriate timeouts and retry logic

### Monitoring

Track key metrics:
- Upload success rate
- Job completion time
- Error frequencies
- User engagement

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Follow existing code style
4. Add tests for new features
5. Submit pull request

## License

MIT License - see [LICENSE](../LICENSE) for details.

/**
 * Tests for OneShot SDK Client
 */
import { OneShotClient, JobType } from '../src';
import {
  mockResponse,
  mockError,
  mockNetworkError,
  mockUserResponse,
  mockPresignResponse,
  mockJobResponse,
  mockJobStatusResponse
} from './utils';

const mockFetch = global.fetch as jest.MockedFunction<typeof fetch>;

describe('OneShotClient', () => {
  let client: OneShotClient;

  beforeEach(() => {
    client = new OneShotClient({
      baseUrl: 'https://api.oneshot.com'
    });
  });

  describe('Authentication', () => {
    it('should login successfully', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(mockUserResponse));

      const result = await client.login('test@example.com', 'password');

      expect(result).toEqual(mockUserResponse);
      expect(client.isAuth()).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.oneshot.com/api/v1/auth/login',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          }),
          body: JSON.stringify({
            email: 'test@example.com',
            password: 'password'
          })
        })
      );
    });

    it('should handle login failure', async () => {
      mockFetch.mockResolvedValueOnce(mockError(401, 'Invalid credentials'));

      await expect(client.login('test@example.com', 'wrong')).rejects.toThrow('Invalid credentials');
      expect(client.isAuth()).toBe(false);
    });

    it('should get current user profile', async () => {
      // Login first
      mockFetch.mockResolvedValueOnce(mockResponse(mockUserResponse));
      await client.login('test@example.com', 'password');

      // Get profile
      mockFetch.mockResolvedValueOnce(mockResponse(mockUserResponse.user));
      const result = await client.getMe();

      expect(result).toEqual(mockUserResponse.user);
      expect(mockFetch).toHaveBeenLastCalledWith(
        'https://api.oneshot.com/api/v1/auth/me',
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Authorization': 'Bearer mock-jwt-token'
          })
        })
      );
    });

    it('should logout successfully', () => {
      client.setAuthToken('test-token');
      expect(client.isAuth()).toBe(true);

      client.logout();
      expect(client.isAuth()).toBe(false);
    });
  });

  describe('File Upload', () => {
    beforeEach(async () => {
      // Login first
      mockFetch.mockResolvedValueOnce(mockResponse(mockUserResponse));
      await client.login('test@example.com', 'password');
    });

    it('should generate presigned URL', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(mockPresignResponse));

      const result = await client.presignUpload('test.jpg', 'image/jpeg', 1024000);

      expect(result).toEqual(mockPresignResponse);
      expect(mockFetch).toHaveBeenLastCalledWith(
        'https://api.oneshot.com/api/v1/uploads/presign',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            filename: 'test.jpg',
            content_type: 'image/jpeg',
            file_size: 1024000
          })
        })
      );
    });

    it('should include idempotency key', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(mockPresignResponse));

      await client.presignUpload('test.jpg', 'image/jpeg', 1024000, 'unique-key-123');

      expect(mockFetch).toHaveBeenLastCalledWith(
        'https://api.oneshot.com/api/v1/uploads/presign',
        expect.objectContaining({
          headers: expect.objectContaining({
            'Idempotency-Key': 'unique-key-123'
          })
        })
      );
    });

    it('should upload file to presigned URL', async () => {
      const mockFile = new Blob(['test'], { type: 'image/jpeg' });
      mockFetch.mockResolvedValueOnce(mockResponse({}));

      await client.uploadFile('https://s3.amazonaws.com/presigned', mockFile, 'image/jpeg');

      expect(mockFetch).toHaveBeenLastCalledWith(
        'https://s3.amazonaws.com/presigned',
        expect.objectContaining({
          method: 'PUT',
          headers: {
            'Content-Type': 'image/jpeg'
          },
          body: mockFile
        })
      );
    });
  });

  describe('Job Management', () => {
    beforeEach(async () => {
      // Login first
      mockFetch.mockResolvedValueOnce(mockResponse(mockUserResponse));
      await client.login('test@example.com', 'password');
    });

    it('should create job successfully', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(mockJobResponse));

      const result = await client.createJob(
        JobType.FACE_RESTORATION,
        'https://example.com/input.jpg',
        { model: 'gfpgan' }
      );

      expect(result).toEqual(mockJobResponse);
      expect(mockFetch).toHaveBeenLastCalledWith(
        'https://api.oneshot.com/api/v1/jobs',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            job_type: 'face_restore',
            input_image_url: 'https://example.com/input.jpg',
            target_image_url: undefined,
            parameters: { model: 'gfpgan' }
          })
        })
      );
    });

    it('should get job status', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(mockJobStatusResponse));

      const result = await client.getJob('job-123');

      expect(result).toEqual(mockJobStatusResponse);
      expect(mockFetch).toHaveBeenLastCalledWith(
        'https://api.oneshot.com/api/v1/jobs/job-123',
        expect.objectContaining({
          method: 'GET'
        })
      );
    });

    it('should list user jobs', async () => {
      const mockJobs = [mockJobStatusResponse];
      mockFetch.mockResolvedValueOnce(mockResponse(mockJobs));

      const result = await client.listJobs(0, 10);

      expect(result).toEqual(mockJobs);
      expect(mockFetch).toHaveBeenLastCalledWith(
        'https://api.oneshot.com/api/v1/jobs?skip=0&limit=10',
        expect.objectContaining({
          method: 'GET'
        })
      );
    });

    it('should list artifacts', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(mockJobStatusResponse));

      const result = await client.listArtifacts('job-123');

      expect(result).toHaveLength(1);
      expect(result[0]).toEqual({
        id: 'job-123_result',
        job_id: 'job-123',
        artifact_type: 'image',
        output_url: 'https://s3.amazonaws.com/bucket/result.jpg',
        created_at: '2023-01-01T00:01:00Z'
      });
    });

    it('should wait for job completion', async () => {
      // First call: job is running
      mockFetch.mockResolvedValueOnce(mockResponse({
        ...mockJobStatusResponse,
        status: 'running',
        progress: 50
      }));

      // Second call: job is completed
      mockFetch.mockResolvedValueOnce(mockResponse(mockJobStatusResponse));

      const progressCallback = jest.fn();
      const result = await client.waitForJob('job-123', {
        pollingInterval: 100,
        onProgress: progressCallback
      });

      expect(result).toEqual(mockJobStatusResponse);
      expect(progressCallback).toHaveBeenCalledTimes(2);
      expect(mockFetch).toHaveBeenCalledTimes(3); // login + 2 polling calls
    });
  });

  describe('Error Handling', () => {
    beforeEach(async () => {
      // Login first
      mockFetch.mockResolvedValueOnce(mockResponse(mockUserResponse));
      await client.login('test@example.com', 'password');
    });

    it('should handle validation errors (422)', async () => {
      mockFetch.mockResolvedValueOnce(mockError(422, 'Validation failed'));

      await expect(client.createJob(JobType.FACE_RESTORATION, 'invalid-url')).rejects.toThrow('Validation failed');
    });

    it('should handle rate limit errors (429)', async () => {
      mockFetch.mockResolvedValueOnce(mockError(429, 'Rate limit exceeded'));

      await expect(client.getJob('job-123')).rejects.toThrow('Rate limit exceeded');
    });

    it('should handle payment required errors (402)', async () => {
      mockFetch.mockResolvedValueOnce(mockError(402, 'Payment required'));

      await expect(client.createJob(JobType.FACE_RESTORATION, 'test-url')).rejects.toThrow('Payment required');
    });

    it('should retry on network errors', async () => {
      mockFetch
        .mockRejectedValueOnce(mockNetworkError())
        .mockResolvedValueOnce(mockResponse(mockJobStatusResponse));

      const result = await client.getJob('job-123');

      expect(result).toEqual(mockJobStatusResponse);
      expect(mockFetch).toHaveBeenCalledTimes(3); // login + retry + success
    });

    it('should throw error when not authenticated', async () => {
      const unauthenticatedClient = new OneShotClient({
        baseUrl: 'https://api.oneshot.com'
      });

      await expect(unauthenticatedClient.getJob('job-123')).rejects.toThrow('Client is not authenticated');
    });
  });

  describe('Configuration', () => {
    it('should use API key for authentication', () => {
      const clientWithApiKey = new OneShotClient({
        baseUrl: 'https://api.oneshot.com',
        apiKey: 'api-key-123'
      });

      expect(clientWithApiKey.isAuth()).toBe(true);
    });

    it('should handle custom timeout', async () => {
      const clientWithTimeout = new OneShotClient({
        baseUrl: 'https://api.oneshot.com',
        timeout: 5000
      });

      clientWithTimeout.setAuthToken('test-token');
      mockFetch.mockResolvedValueOnce(mockResponse(mockJobStatusResponse));

      await clientWithTimeout.getJob('job-123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          signal: expect.any(AbortSignal)
        })
      );
    });
  });
});
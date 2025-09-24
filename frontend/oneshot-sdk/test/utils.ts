/**
 * Test utilities and mocks
 */

export const mockResponse = (data: any, status = 200) => {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    text: () => Promise.resolve(JSON.stringify(data)),
    json: () => Promise.resolve(data)
  } as Response);
};

export const mockError = (status: number, message = 'Error') => {
  return Promise.resolve({
    ok: false,
    status,
    statusText: message,
    text: () => Promise.resolve(JSON.stringify({ error: { message } }))
  } as Response);
};

export const mockNetworkError = () => {
  return Promise.reject(new TypeError('Network request failed'));
};

export const mockTimeout = () => {
  return Promise.reject(new DOMException('The operation was aborted', 'AbortError'));
};

export const mockUserResponse = {
  access_token: 'mock-jwt-token',
  token_type: 'bearer',
  user: {
    id: 'user-123',
    email: 'test@example.com',
    credits: 50,
    subscription_status: 'active',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z'
  }
};

export const mockPresignResponse = {
  presigned_url: 'https://s3.amazonaws.com/bucket/presigned-url',
  upload_id: 'upload-123',
  expires_in: 3600,
  max_file_size: 20971520,
  allowed_mime_types: ['image/jpeg', 'image/png']
};

export const mockJobResponse = {
  job_id: 'job-123',
  status: 'pending',
  estimated_time: 60,
  credits_cost: 1
};

export const mockJobStatusResponse = {
  job_id: 'job-123',
  status: 'succeeded',
  progress: 100,
  result_url: 'https://s3.amazonaws.com/bucket/result.jpg',
  created_at: '2023-01-01T00:00:00Z',
  completed_at: '2023-01-01T00:01:00Z'
};
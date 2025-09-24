/**
 * Tests for HTTP Client
 */
import { FetchHttpClient } from '../src/http-client';
import { mockResponse, mockError, mockNetworkError } from './utils';

const mockFetch = global.fetch as jest.MockedFunction<typeof fetch>;

describe('FetchHttpClient', () => {
  let client: FetchHttpClient;

  beforeEach(() => {
    client = new FetchHttpClient('https://api.example.com');
  });

  describe('Basic HTTP Methods', () => {
    it('should make GET request', async () => {
      const mockData = { message: 'success' };
      mockFetch.mockResolvedValueOnce(mockResponse(mockData));

      const result = await client.get('/test');

      expect(result).toEqual(mockData);
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/test',
        expect.objectContaining({
          method: 'GET'
        })
      );
    });

    it('should make POST request with data', async () => {
      const mockData = { id: 1 };
      const requestData = { name: 'test' };
      mockFetch.mockResolvedValueOnce(mockResponse(mockData));

      const result = await client.post('/test', requestData);

      expect(result).toEqual(mockData);
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/test',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(requestData)
        })
      );
    });

    it('should make PUT request', async () => {
      const mockData = { updated: true };
      mockFetch.mockResolvedValueOnce(mockResponse(mockData));

      const result = await client.put('/test', { data: 'value' });

      expect(result).toEqual(mockData);
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/test',
        expect.objectContaining({
          method: 'PUT'
        })
      );
    });

    it('should make DELETE request', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({}));

      await client.delete('/test');

      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/test',
        expect.objectContaining({
          method: 'DELETE'
        })
      );
    });
  });

  describe('Authentication', () => {
    it('should include bearer token in headers', async () => {
      client.setBearerToken('test-token');
      mockFetch.mockResolvedValueOnce(mockResponse({}));

      await client.get('/test');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': 'Bearer test-token'
          })
        })
      );
    });

    it('should clear bearer token', async () => {
      client.setBearerToken('test-token');
      client.clearBearerToken();
      mockFetch.mockResolvedValueOnce(mockResponse({}));

      await client.get('/test');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.not.objectContaining({
            'Authorization': expect.any(String)
          })
        })
      );
    });
  });

  describe('Request Options', () => {
    it('should include custom headers', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({}));

      await client.get('/test', {
        headers: { 'Custom-Header': 'value' }
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Custom-Header': 'value'
          })
        })
      );
    });

    it('should include idempotency key', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({}));

      await client.post('/test', {}, {
        idempotencyKey: 'unique-key-123'
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Idempotency-Key': 'unique-key-123'
          })
        })
      );
    });
  });

  describe('Retry Logic', () => {
    it('should retry on network errors', async () => {
      mockFetch
        .mockRejectedValueOnce(mockNetworkError())
        .mockResolvedValueOnce(mockResponse({ success: true }));

      const result = await client.get('/test');

      expect(result).toEqual({ success: true });
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('should retry on 5xx errors', async () => {
      mockFetch
        .mockResolvedValueOnce(mockError(500, 'Internal Server Error'))
        .mockResolvedValueOnce(mockResponse({ success: true }));

      const result = await client.get('/test');

      expect(result).toEqual({ success: true });
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('should not retry on 4xx errors', async () => {
      mockFetch.mockResolvedValueOnce(mockError(400, 'Bad Request'));

      await expect(client.get('/test')).rejects.toThrow('Bad Request');
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    it('should respect retry attempts limit', async () => {
      const clientWithRetries = new FetchHttpClient('https://api.example.com', 30000, 2);
      
      mockFetch
        .mockRejectedValueOnce(mockNetworkError())
        .mockRejectedValueOnce(mockNetworkError())
        .mockRejectedValueOnce(mockNetworkError());

      await expect(clientWithRetries.get('/test')).rejects.toThrow('Network connection failed');
      expect(mockFetch).toHaveBeenCalledTimes(2); // Original + 1 retry (2 retries max)
    });
  });

  describe('Error Handling', () => {
    it('should handle response with empty body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: () => Promise.resolve('')
      } as Response);

      const result = await client.get('/test');

      expect(result).toEqual({});
    });

    it('should handle malformed JSON response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: () => Promise.resolve('invalid json')
      } as Response);

      const result = await client.get('/test');

      expect(result).toEqual({});
    });

    it('should handle timeout', async () => {
      mockFetch.mockRejectedValueOnce(new DOMException('The operation was aborted', 'AbortError'));

      await expect(client.get('/test')).rejects.toThrow('Request timeout');
    });
  });
});
import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { fetchJson } from './client.js';

const originalFetch = global.fetch;

describe('fetchJson', () => {
  let fetchMock;

  beforeEach(() => {
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    fetchMock.mockReset();
    global.fetch = originalFetch;
  });

  it('prefixes path with /api and includes credentials', async () => {
    const responseData = { ok: true };
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue(responseData),
    });

    const result = await fetchJson('/health');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/health');
    expect(options.credentials).toBe('include');
    expect(options.method).toBe('GET');
    expect(result).toEqual(responseData);
  });

  it('sends JSON payloads and sets content-type header', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({ success: true }),
    });

    await fetchJson('/tests', {
      method: 'POST',
      json: { value: 42 },
      headers: { 'X-Custom': 'abc' },
    });

    const [, options] = fetchMock.mock.calls[0];
    expect(options.method).toBe('POST');
    expect(options.body).toBe(JSON.stringify({ value: 42 }));
    expect(options.headers['Content-Type']).toBe('application/json');
    expect(options.headers['X-Custom']).toBe('abc');
  });

  it('throws ApiError on non-2xx responses with error payload', async () => {
    const errorPayload = { error: 'bad_request' };
    fetchMock.mockResolvedValue({
      ok: false,
      status: 400,
      json: jest.fn().mockResolvedValue(errorPayload),
    });

    await expect(fetchJson('/fail')).rejects.toMatchObject({
      name: 'ApiError',
      status: 400,
      message: 'bad_request',
      body: errorPayload,
    });
  });

  it('throws ApiError with status 0 on network failure', async () => {
    fetchMock.mockRejectedValue(new Error('Network down'));

    await expect(fetchJson('/unreachable')).rejects.toMatchObject({
      name: 'ApiError',
      status: 0,
      message: 'Backend unavailable',
    });
  });
});

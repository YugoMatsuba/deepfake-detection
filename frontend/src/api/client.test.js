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

  it('throws ApiError on 401 for /auth/me (prevents infinite loop)', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 401,
      json: jest.fn().mockResolvedValue({ error: 'unauthorized' }),
    });

    await expect(fetchJson('/auth/me')).rejects.toMatchObject({
      name: 'ApiError',
      status: 401,
      message: 'Unauthorized',
    });
  });

  it('redirects to /login on 401 for non-auth endpoints', async () => {
    const originalLocation = window.location;
    delete window.location;
    window.location = { href: '' };

    fetchMock.mockResolvedValue({
      ok: false,
      status: 401,
      json: jest.fn().mockResolvedValue({ error: 'unauthorized' }),
    });

    // Start the promise but don't await (it never resolves)
    fetchJson('/protected');

    // Give it a tick to process
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(window.location.href).toBe('/login');

    // Cleanup
    window.location = originalLocation;
  });
});

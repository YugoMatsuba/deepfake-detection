import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { apiFetch } from './fetch.js';

const originalFetch = global.fetch;
const originalLocation = window.location;

describe('apiFetch', () => {
  let fetchMock;

  beforeEach(() => {
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    fetchMock.mockReset();
    global.fetch = originalFetch;
    Object.defineProperty(window, 'location', {
      configurable: true,
      enumerable: true,
      value: originalLocation,
    });
  });

  it('makes request with JSON headers and includes credentials', async () => {
    const data = { value: 123 };
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue(data),
    });

    const result = await apiFetch('/api/test', { method: 'POST', body: JSON.stringify({}) });

    expect(fetchMock).toHaveBeenCalledWith('/api/test', expect.objectContaining({
      credentials: 'include',
      method: 'POST',
    }));
    expect(result).toEqual(data);
  });

  it('redirects to /login on 401 responses', async () => {
    const mockLocation = { href: '/' };
    Object.defineProperty(window, 'location', {
      configurable: true,
      enumerable: true,
      value: mockLocation,
    });

    fetchMock.mockResolvedValue({
      ok: false,
      status: 401,
      json: jest.fn(),
    });

    // apiFetch returns a never-resolving promise on 401 (page redirects before it matters)
    // Just verify the redirect happens, don't wait for promise
    const promise = apiFetch('/api/protected');

    // Give it a tick to process the response
    await new Promise(resolve => setImmediate(resolve));

    expect(mockLocation.href).toBe('/login');
  });

  it('throws structured error on 403 responses', async () => {
    const payload = { error: 'access_denied' };
    fetchMock.mockResolvedValue({
      ok: false,
      status: 403,
      json: jest.fn().mockResolvedValue(payload),
    });

    await expect(apiFetch('/api/protected')).rejects.toMatchObject({
      status: 403,
      body: payload,
    });
  });

  it('throws descriptive error for other non-ok responses', async () => {
    const payload = { error: 'not_found' };
    fetchMock.mockResolvedValue({
      ok: false,
      status: 404,
      json: jest.fn().mockResolvedValue(payload),
    });

    await expect(apiFetch('/api/missing')).rejects.toMatchObject({
      status: 404,
      message: 'not_found',
    });
  });
});

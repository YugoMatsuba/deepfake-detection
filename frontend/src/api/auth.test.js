import { jest, describe, it, expect, beforeEach } from '@jest/globals';

const mockFetchJson = jest.fn();

await jest.unstable_mockModule('./client.js', () => ({
  fetchJson: mockFetchJson,
}));

const { apiLogin, apiSignUp, apiMe, apiLogout } = await import('./auth.js');

describe('auth API helpers', () => {
  beforeEach(() => {
    mockFetchJson.mockReset();
  });

  it('apiLogin posts username and password', async () => {
    const payload = { user: { id: 1 } };
    mockFetchJson.mockResolvedValue(payload);

    const data = await apiLogin({ username: 'alice', password: 'secret' });

    expect(mockFetchJson).toHaveBeenCalledWith('/auth/login', {
      method: 'POST',
      json: { username: 'alice', password: 'secret' },
    });
    expect(data).toBe(payload);
  });

  it('apiSignUp posts username and password', async () => {
    mockFetchJson.mockResolvedValue({ user: { id: 2 } });

    await apiSignUp({ username: 'bob', password: 'pw' });

    expect(mockFetchJson).toHaveBeenCalledWith('/auth/signup', {
      method: 'POST',
      json: { username: 'bob', password: 'pw' },
    });
  });

  it('apiMe fetches current user', async () => {
    mockFetchJson.mockResolvedValue({ user: { id: 3 } });

    const result = await apiMe();

    expect(mockFetchJson).toHaveBeenCalledWith('/auth/me');
    expect(result).toEqual({ user: { id: 3 } });
  });

  it('apiLogout posts to logout endpoint', async () => {
    mockFetchJson.mockResolvedValue(null);

    await apiLogout();

    expect(mockFetchJson).toHaveBeenCalledWith('/auth/logout', {
      method: 'POST',
    });
  });
});

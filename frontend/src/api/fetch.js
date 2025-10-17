/**
 * Global fetch wrapper with auth handling and credentials.
 *
 * Features:
 * - Always includes credentials for session cookies
 * - Auto-redirects to /login on 401 (session expired)
 * - Throws structured errors for 403 (access denied)
 * - Handles JSON parsing and error responses
 */

export async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    credentials: 'include', // Always include cookies for session auth
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    }
  });

  // 401 Unauthorized → session expired, auto logout and redirect
  if (res.status === 401) {
    // Clear any local state if needed
    window.location.href = '/login';
    throw new Error('Session expired. Please login again.');
  }

  // 403 Forbidden → access denied (insufficient permissions)
  if (res.status === 403) {
    const data = await res.json().catch(() => ({ error: 'access_denied' }));
    const err = new Error(data.error || 'Access denied');
    err.status = 403;
    err.body = data;
    throw err;
  }

  // Other error responses
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
    const err = new Error(data.error || `Request failed with status ${res.status}`);
    err.status = res.status;
    err.body = data;
    throw err;
  }

  // Success - parse JSON
  return res.json();
}

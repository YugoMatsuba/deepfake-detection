// API client with credentials:'include' and error normalization
export async function fetchJson(path, options = {}) {
  const {
    method = 'GET',
    json,
    headers = {},
    body,
    ...fetchOptions
  } = options;

  // Always prefix with /api and include credentials
  const url = `/api${path}`;
  const config = {
    method,
    credentials: 'include',
    headers: {
      ...headers,
    },
    ...fetchOptions,
  };

  // If JSON data provided, stringify and set content type
  if (json) {
    config.body = JSON.stringify(json);
    config.headers['Content-Type'] = 'application/json';
  } else if (body) {
    config.body = body;
  }

  try {
    const response = await fetch(url, config);
    
    // Try to parse JSON response
    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    // Handle non-2xx responses
    if (!response.ok) {
      // Handle session expired
      if (response.status === 401) {
        // Don't redirect if checking auth status (prevents infinite loop on login page)
        // AuthProvider calls /auth/me on mount - let it handle 401 gracefully
        if (path === '/auth/me') {
          const error = new Error('Unauthorized');
          error.name = 'ApiError';
          error.status = 401;
          error.message = 'Unauthorized';
          error.body = data;
          throw error;
        }

        // For all other 401s, redirect to login
        window.location.href = '/login';
        // Never-resolving promise prevents components from catching error and updating state
        // No memory leak: page navigates away immediately, entire context is destroyed
        return new Promise(() => {});
      }

      const error = new Error(data?.error || `HTTP ${response.status}`);
      error.name = 'ApiError';
      error.status = response.status;
      error.message = data?.error || `HTTP ${response.status}`;
      error.body = data;
      throw error;
    }

    return data;
  } catch (err) {
    // Re-throw API errors
    if (err.name === 'ApiError') {
      throw err;
    }

    // Network failure
    const error = new Error('Backend unavailable');
    error.name = 'ApiError';
    error.status = 0;
    error.message = 'Backend unavailable';
    throw error;
  }
}
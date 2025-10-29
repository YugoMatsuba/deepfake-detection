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
        window.location.href = '/login';
        // Return a promise that never resolves - page will redirect before it matters
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
    // Don't catch 401 redirects - let them proceed
    if (err === undefined) {
      return new Promise(() => {}); // Should never happen, but just in case
    }

    // Network/fetch errors (backend down)
    if (err.name === 'ApiError') {
      throw err; // Re-throw API errors
    }

    // Network failure
    const error = new Error('Backend unavailable');
    error.name = 'ApiError';
    error.status = 0;
    error.message = 'Backend unavailable';
    throw error;
  }
}
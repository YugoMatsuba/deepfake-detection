import { fetchJson } from './client.js';

// Login user with username/password
export async function apiLogin({ username, password }) {
  const data = await fetchJson('/auth/login', {
    method: 'POST',
    json: { username, password }
  });
  return data; // Should return { user: {...} }
}

export async function apiSignUp({ username, password}) {
  const data = await fetchJson('/auth/signup', {
    method: 'POST',
    json: { username, password }
  });
  // Expect your backend to return: { user: {...} }
  return data;
}

// Get current user info
export async function apiMe() {
  const data = await fetchJson('/auth/me');
  return data; // Should return { user: {...} }
}

// Logout current user
export async function apiLogout() {
  await fetchJson('/auth/logout', {
    method: 'POST'
  });
  return null;
}
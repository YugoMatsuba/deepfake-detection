/**
 * Admin API client for dashboard operations.
 *
 * All endpoints require admin or owner role.
 * Uses global apiFetch for auth handling and credentials.
 */

import { apiFetch } from './fetch.js';

const BASE_URL = '/api/admin';

// ============================================================================
// User Approval Management
// ============================================================================

/**
 * Get list of users awaiting approval.
 * @param {number} limit - Max results (default 100, max 500)
 * @returns {Promise<{users: Array}>}
 */
export async function getPendingUsers(limit = 100) {
  return apiFetch(`${BASE_URL}/pending-users?limit=${limit}`);
}

/**
 * Approve pending user.
 * @param {number} userId - User ID to approve
 * @returns {Promise<{message: string, user_id: number}>}
 */
export async function approveUser(userId) {
  return apiFetch(`${BASE_URL}/users/${userId}/approve`, {
    method: 'POST'
  });
}

/**
 * Reject pending user (hard delete).
 * @param {number} userId - User ID to reject
 * @returns {Promise<{message: string, username: string}>}
 */
export async function rejectUser(userId) {
  return apiFetch(`${BASE_URL}/users/${userId}/reject`, {
    method: 'POST'
  });
}

// ============================================================================
// Audit Logs
// ============================================================================

/**
 * Get audit logs with pagination and optional filtering.
 * @param {Object} params
 * @param {number} params.limit - Max results (default 100, max 500)
 * @param {number} params.offset - Offset for pagination (default 0)
 * @param {number} params.userId - Optional filter by user ID
 * @returns {Promise<{logs: Array, total: number, limit: number, offset: number}>}
 */
export async function getAuditLogs({ limit = 50, offset = 0, userId = null } = {}) {
  const params = new URLSearchParams({ limit, offset });
  if (userId) params.set('user_id', userId);

  return apiFetch(`${BASE_URL}/audit-logs?${params}`);
}

// ============================================================================
// Analysis Management
// ============================================================================

/**
 * Get all analyses with pagination and optional filtering.
 * @param {Object} params
 * @param {number} params.limit - Max results (default 50, max 500)
 * @param {number} params.offset - Offset for pagination (default 0)
 * @param {number} params.userId - Optional filter by user ID
 * @param {string} params.status - Optional filter by status
 * @returns {Promise<{analyses: Array, total: number, limit: number, offset: number}>}
 */
export async function getAllAnalyses({ limit = 50, offset = 0, userId = null, status = null } = {}) {
  const params = new URLSearchParams({ limit, offset });
  if (userId) params.set('user_id', userId);
  if (status) params.set('status', status);

  return apiFetch(`${BASE_URL}/analyses?${params}`);
}

/**
 * Reassign analysis to different user.
 * @param {string} analysisId - Analysis ID (UUID)
 * @param {number} newUserId - Target user ID
 * @returns {Promise<{message: string, analysis_id: string, new_user_id: number}>}
 */
export async function reassignAnalysis(analysisId, newUserId) {
  return apiFetch(`${BASE_URL}/analyses/${analysisId}/reassign`, {
    method: 'POST',
    body: JSON.stringify({ new_user_id: newUserId })
  });
}

/**
 * Search users by username for autocomplete.
 * @param {string} query - Search term (min 1 char)
 * @param {number} limit - Max results (default 20, max 100)
 * @returns {Promise<{users: Array<{id: number, username: string}>}>}
 */
export async function searchUsers(query, limit = 20) {
  const params = new URLSearchParams({
    q: query ? query.trim() : "",
    limit
  });
  return apiFetch(`${BASE_URL}/users/search?${params}`);
}

// ============================================================================
// Role Management (Owner Only)
// ============================================================================

/**
 * Promote user to admin role.
 * Requires owner role.
 * @param {number} userId - User ID to promote
 * @returns {Promise<{message: string, user_id: number}>}
 */
export async function promoteUser(userId) {
  return apiFetch(`${BASE_URL}/users/${userId}/promote`, {
    method: 'POST'
  });
}

/**
 * Demote admin to user role.
 * Requires owner role. Cannot demote last admin.
 * @param {number} userId - User ID to demote
 * @returns {Promise<{message: string, user_id: number}>}
 */
export async function demoteUser(userId) {
  return apiFetch(`${BASE_URL}/users/${userId}/demote`, {
    method: 'POST'
  });
}

/**
 * Deactivate user.
 * Requires owner role. Cannot deactivate last admin or owner.
 * @param {number} userId - User ID to deactivate
 * @returns {Promise<{message: string, user_id: number}>}
 */
export async function deactivateUser(userId) {
  return apiFetch(`${BASE_URL}/users/${userId}/deactivate`, {
    method: 'POST'
  });
}

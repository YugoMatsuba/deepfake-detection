import { jest, describe, it, expect, beforeEach } from '@jest/globals';

const mockApiFetch = jest.fn();

await jest.unstable_mockModule('./fetch.js', () => ({
  apiFetch: mockApiFetch,
}));

const {
  getPendingUsers,
  approveUser,
  rejectUser,
  getAuditLogs,
  getAllAnalyses,
  reassignAnalysis,
  searchUsers,
  promoteUser,
  demoteUser,
  deactivateUser,
} = await import('./admin.js');

describe('admin API helpers', () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it('getPendingUsers uses default limit', async () => {
    mockApiFetch.mockResolvedValue({ users: [] });

    await getPendingUsers();

    expect(mockApiFetch).toHaveBeenCalledWith('/api/admin/pending-users?limit=100');
  });

  it('approveUser posts to approval endpoint', async () => {
    mockApiFetch.mockResolvedValue({ ok: true });

    await approveUser(10);

    expect(mockApiFetch).toHaveBeenCalledWith('/api/admin/users/10/approve', {
      method: 'POST',
    });
  });

  it('rejectUser posts to rejection endpoint', async () => {
    mockApiFetch.mockResolvedValue({ ok: true });

    await rejectUser(7);

    expect(mockApiFetch).toHaveBeenCalledWith('/api/admin/users/7/reject', {
      method: 'POST',
    });
  });

  it('getAuditLogs builds query string with optional params', async () => {
    mockApiFetch.mockResolvedValue({ logs: [] });

    await getAuditLogs({ limit: 10, offset: 5, userId: 3 });

    expect(mockApiFetch).toHaveBeenCalledWith('/api/admin/audit-logs?limit=10&offset=5&user_id=3');
  });

  it('getAllAnalyses supports status filtering', async () => {
    mockApiFetch.mockResolvedValue({ analyses: [] });

    await getAllAnalyses({ status: 'queued', userId: 12 });

    expect(mockApiFetch).toHaveBeenCalledWith('/api/admin/analyses?limit=50&offset=0&user_id=12&status=queued');
  });

  it('reassignAnalysis posts payload as JSON string', async () => {
    mockApiFetch.mockResolvedValue({ ok: true });

    await reassignAnalysis('analysis-id', 42);

    expect(mockApiFetch).toHaveBeenCalledWith('/api/admin/analyses/analysis-id/reassign', {
      method: 'POST',
      body: JSON.stringify({ new_user_id: 42 }),
    });
  });

  it('searchUsers trims query and sets default limit', async () => {
    mockApiFetch.mockResolvedValue({ users: [] });

    await searchUsers('  alice  ');

    expect(mockApiFetch).toHaveBeenCalledWith('/api/admin/users/search?q=alice&limit=20');
  });

  it('promoteUser, demoteUser, deactivateUser post to role endpoints', async () => {
    mockApiFetch.mockResolvedValue({ ok: true });

    await promoteUser(1);
    await demoteUser(2);
    await deactivateUser(3);

    expect(mockApiFetch).toHaveBeenNthCalledWith(1, '/api/admin/users/1/promote', { method: 'POST' });
    expect(mockApiFetch).toHaveBeenNthCalledWith(2, '/api/admin/users/2/demote', { method: 'POST' });
    expect(mockApiFetch).toHaveBeenNthCalledWith(3, '/api/admin/users/3/deactivate', { method: 'POST' });
  });
});

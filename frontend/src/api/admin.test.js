import { jest, describe, it, expect, beforeEach } from '@jest/globals';

const mockFetchJson = jest.fn();

await jest.unstable_mockModule('./client.js', () => ({
  fetchJson: mockFetchJson,
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
    mockFetchJson.mockReset();
  });

  it('getPendingUsers uses default limit', async () => {
    mockFetchJson.mockResolvedValue({ users: [] });

    await getPendingUsers();

    expect(mockFetchJson).toHaveBeenCalledWith('/admin/pending-users?limit=100');
  });

  it('approveUser posts to approval endpoint', async () => {
    mockFetchJson.mockResolvedValue({ ok: true });

    await approveUser(10);

    expect(mockFetchJson).toHaveBeenCalledWith('/admin/users/10/approve', {
      method: 'POST',
    });
  });

  it('rejectUser posts to rejection endpoint', async () => {
    mockFetchJson.mockResolvedValue({ ok: true });

    await rejectUser(7);

    expect(mockFetchJson).toHaveBeenCalledWith('/admin/users/7/reject', {
      method: 'POST',
    });
  });

  it('getAuditLogs builds query string with optional params', async () => {
    mockFetchJson.mockResolvedValue({ logs: [] });

    await getAuditLogs({ limit: 10, offset: 5, userId: 3 });

    expect(mockFetchJson).toHaveBeenCalledWith('/admin/audit-logs?limit=10&offset=5&user_id=3');
  });

  it('getAllAnalyses supports status filtering', async () => {
    mockFetchJson.mockResolvedValue({ analyses: [] });

    await getAllAnalyses({ status: 'queued', userId: 12 });

    expect(mockFetchJson).toHaveBeenCalledWith('/admin/analyses?limit=50&offset=0&user_id=12&status=queued');
  });

  it('reassignAnalysis posts payload as JSON', async () => {
    mockFetchJson.mockResolvedValue({ ok: true });

    await reassignAnalysis('analysis-id', 42);

    expect(mockFetchJson).toHaveBeenCalledWith('/admin/analyses/analysis-id/reassign', {
      method: 'POST',
      json: { new_user_id: 42 },
    });
  });

  it('searchUsers trims query and sets default limit', async () => {
    mockFetchJson.mockResolvedValue({ users: [] });

    await searchUsers('  alice  ');

    expect(mockFetchJson).toHaveBeenCalledWith('/admin/users/search?q=alice&limit=20');
  });

  it('promoteUser, demoteUser, deactivateUser post to role endpoints', async () => {
    mockFetchJson.mockResolvedValue({ ok: true });

    await promoteUser(1);
    await demoteUser(2);
    await deactivateUser(3);

    expect(mockFetchJson).toHaveBeenNthCalledWith(1, '/admin/users/1/promote', { method: 'POST' });
    expect(mockFetchJson).toHaveBeenNthCalledWith(2, '/admin/users/2/demote', { method: 'POST' });
    expect(mockFetchJson).toHaveBeenNthCalledWith(3, '/admin/users/3/deactivate', { method: 'POST' });
  });
});

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../app/useAuth.js";
import * as adminApi from "../api/admin.js";

export default function AdminDashboard() {
  const [activeTab, setActiveTab] = useState("pending");
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isOwner = user?.role === 'owner';

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-semibold">Admin Dashboard</h1>
            <p className="text-gray-600 text-sm">
              Logged in as {user?.username} ({user?.role})
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => navigate("/upload")}
              className="px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-900 hover:bg-gray-50 transition"
            >
              Go to Upload
            </button>
            <button
              onClick={logout}
              className="px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 transition"
            >
              Logout
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-4">
          <div className="flex border-b border-gray-200">
            <TabButton
              active={activeTab === "pending"}
              onClick={() => setActiveTab("pending")}
            >
              Pending Users
            </TabButton>
            <TabButton
              active={activeTab === "logs"}
              onClick={() => setActiveTab("logs")}
            >
              Audit Logs
            </TabButton>
            <TabButton
              active={activeTab === "analyses"}
              onClick={() => setActiveTab("analyses")}
            >
              Analyses
            </TabButton>
            {isOwner && (
              <TabButton
                active={activeTab === "roles"}
                onClick={() => setActiveTab("roles")}
              >
                Role Management
              </TabButton>
            )}
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {activeTab === "pending" && <PendingUsersTab />}
            {activeTab === "logs" && <AuditLogsTab />}
            {activeTab === "analyses" && <AnalysesTab />}
            {activeTab === "roles" && isOwner && <RoleManagementTab />}
          </div>
        </div>
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-6 py-3 font-medium transition ${
        active
          ? "border-b-2 border-blue-600 text-blue-600"
          : "text-gray-600 hover:text-gray-900"
      }`}
    >
      {children}
    </button>
  );
}

// ============================================================================
// Tab 1: Pending Users
// ============================================================================

function PendingUsersTab() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.getPendingUsers();
      setUsers(data.users);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleApprove = async (userId) => {
    try {
      await adminApi.approveUser(userId);
      // Optimistic UI: remove immediately
      setUsers(users.filter(u => u.id !== userId));
    } catch (err) {
      alert(`Failed to approve user: ${err.message}`);
      // Rollback: reload
      loadUsers();
    }
  };

  const handleReject = async (userId, username) => {
    if (!confirm(`Delete user "${username}"? This cannot be undone.`)) {
      return;
    }

    try {
      await adminApi.rejectUser(userId);
      // Optimistic UI: remove immediately
      setUsers(users.filter(u => u.id !== userId));
    } catch (err) {
      alert(`Failed to reject user: ${err.message}`);
      // Rollback: reload
      loadUsers();
    }
  };

  if (loading) return <div className="text-gray-600">Loading...</div>;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (users.length === 0) {
    return <div className="text-gray-600 text-center py-8">No pending users</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">Username</th>
            <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">Created</th>
            <th className="text-right px-4 py-2 text-sm font-semibold text-gray-700">Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id} className="border-b border-gray-100 hover:bg-gray-50">
              <td className="px-4 py-3">{user.username}</td>
              <td className="px-4 py-3 text-sm text-gray-600">
                {new Date(user.created_at).toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={() => handleApprove(user.id)}
                  className="px-3 py-1 rounded bg-green-600 text-white text-sm hover:bg-green-700 transition mr-2"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleReject(user.id, user.username)}
                  className="px-3 py-1 rounded bg-red-600 text-white text-sm hover:bg-red-700 transition"
                >
                  Reject
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ============================================================================
// Tab 2: Audit Logs
// ============================================================================

function AuditLogsTab() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const limit = 50;

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.getAuditLogs({ limit, offset });
      setLogs(data.logs);
      setTotal(data.total);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [offset]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const loadMore = () => {
    setOffset(offset + limit);
  };

  if (loading && logs.length === 0) return <div className="text-gray-600">Loading...</div>;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (logs.length === 0) {
    return <div className="text-gray-600 text-center py-8">No audit logs</div>;
  }

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">Timestamp</th>
              <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">User</th>
              <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">Event</th>
              <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">IP</th>
              <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">Details</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id} className="border-b border-gray-100 even:bg-gray-50">
                <td className="px-4 py-2 text-sm">
                  {new Date(log.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2 text-sm">{log.username || '-'}</td>
                <td className="px-4 py-2 text-sm">{log.event}</td>
                <td className="px-4 py-2 text-sm text-gray-600">{log.ip}</td>
                <td className="px-4 py-2 text-sm text-gray-600">
                  {log.details ? (
                    <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                      {JSON.stringify(log.details).slice(0, 50)}...
                    </code>
                  ) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {logs.length < total && (
        <div className="mt-4 text-center">
          <button
            onClick={loadMore}
            disabled={loading}
            className="px-4 py-2 rounded-lg border border-blue-600 bg-blue-600 text-white hover:bg-blue-700 transition disabled:opacity-50"
          >
            {loading ? 'Loading...' : `Load More (${logs.length} of ${total})`}
          </button>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Tab 3: Analyses
// ============================================================================

function AnalysesTab() {
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [reassignModal, setReassignModal] = useState(null);
  const limit = 50;

  const loadAnalyses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.getAllAnalyses({ limit, offset });
      setAnalyses(data.analyses);
      setTotal(data.total);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [offset]);

  useEffect(() => {
    loadAnalyses();
  }, [loadAnalyses]);

  const loadMore = () => {
    setOffset(offset + limit);
  };

  const handleReassign = (analysis) => {
    setReassignModal(analysis);
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'succeeded': return 'bg-green-100 text-green-800';
      case 'failed': return 'bg-red-100 text-red-800';
      case 'running': return 'bg-blue-100 text-blue-800';
      case 'queued': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading && analyses.length === 0) return <div className="text-gray-600">Loading...</div>;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (analyses.length === 0) {
    return <div className="text-gray-600 text-center py-8">No analyses found</div>;
  }

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">ID</th>
              <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">User</th>
              <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">Status</th>
              <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">Created</th>
              <th className="text-right px-4 py-2 text-sm font-semibold text-gray-700">Actions</th>
            </tr>
          </thead>
          <tbody>
            {analyses.map((analysis) => (
              <tr key={analysis.id} className="border-b border-gray-100 even:bg-gray-50">
                <td className="px-4 py-2 text-sm font-mono">{analysis.id.slice(0, 8)}...</td>
                <td className="px-4 py-2 text-sm">{analysis.username}</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(analysis.status)}`}>
                    {analysis.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm text-gray-600">
                  {new Date(analysis.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2 text-right">
                  <button
                    onClick={() => handleReassign(analysis)}
                    className="px-3 py-1 rounded bg-blue-600 text-white text-sm hover:bg-blue-700 transition"
                  >
                    Reassign
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {analyses.length < total && (
        <div className="mt-4 text-center">
          <button
            onClick={loadMore}
            disabled={loading}
            className="px-4 py-2 rounded-lg border border-blue-600 bg-blue-600 text-white hover:bg-blue-700 transition disabled:opacity-50"
          >
            {loading ? 'Loading...' : `Load More (${analyses.length} of ${total})`}
          </button>
        </div>
      )}

      {reassignModal && (
        <ReassignModal
          analysis={reassignModal}
          onClose={() => setReassignModal(null)}
          onSuccess={loadAnalyses}
        />
      )}
    </div>
  );
}

// ============================================================================
// Reassign Modal
// ============================================================================

function ReassignModal({ analysis, onClose, onSuccess }) {
  const [query, setQuery] = useState("");
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [loading, setLoading] = useState(false);

  // Debounced search
  useEffect(() => {
    if (query.length === 0) {
      setUsers([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const data = await adminApi.searchUsers(query);
        setUsers(data.users);
      } catch (err) {
        console.error('Search failed:', err);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  const handleReassign = async () => {
    if (!selectedUser) return;

    if (!confirm(`Reassign analysis to ${selectedUser.username}?`)) {
      return;
    }

    setLoading(true);
    try {
      await adminApi.reassignAnalysis(analysis.id, selectedUser.id);
      onSuccess();
      onClose();
    } catch (err) {
      alert(`Failed to reassign: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 grid place-items-center z-50" onClick={onClose}>
      <div className="bg-white rounded-lg p-6 w-[min(92vw,500px)]" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-semibold mb-4">Reassign Analysis</h2>
        <p className="text-sm text-gray-600 mb-4">
          Analysis ID: <code className="font-mono bg-gray-100 px-2 py-1 rounded">{analysis.id}</code>
        </p>
        <p className="text-sm text-gray-600 mb-4">
          Current user: <strong>{analysis.username}</strong>
        </p>

        <div className="mb-4">
          <label className="block text-sm font-medium mb-1">Search for new user:</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type username..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoFocus
          />
        </div>

        {users.length > 0 && (
          <div className="mb-4 max-h-48 overflow-y-auto border border-gray-200 rounded-lg">
            {users.map((user) => (
              <button
                key={user.id}
                onClick={() => setSelectedUser(user)}
                className={`w-full text-left px-3 py-2 hover:bg-blue-50 transition ${
                  selectedUser?.id === user.id ? 'bg-blue-100' : ''
                }`}
              >
                {user.username}
              </button>
            ))}
          </div>
        )}

        {selectedUser && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm">
              Selected: <strong>{selectedUser.username}</strong>
            </p>
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 transition"
          >
            Cancel
          </button>
          <button
            onClick={handleReassign}
            disabled={!selectedUser || loading}
            className="px-4 py-2 rounded-lg border border-blue-600 bg-blue-600 text-white hover:bg-blue-700 transition disabled:opacity-50"
          >
            {loading ? 'Reassigning...' : 'Reassign'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Tab 4: Role Management (Owner Only)
// ============================================================================

function RoleManagementTab() {
  const [query, setQuery] = useState("");
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);

  // Search users
  useEffect(() => {
    if (query.length === 0) {
      setUsers([]);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await adminApi.searchUsers(query);
        setUsers(data.users);
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  const handlePromote = async (userId, username) => {
    if (!confirm(`Promote "${username}" to admin?`)) return;

    try {
      await adminApi.promoteUser(userId);
      alert(`${username} promoted to admin`);
      // Reload search
      const data = await adminApi.searchUsers(query);
      setUsers(data.users);
    } catch (err) {
      alert(`Failed: ${err.message}`);
    }
  };

  const handleDemote = async (userId, username) => {
    if (!confirm(`Demote "${username}" to user? This will remove admin privileges.`)) return;

    try {
      await adminApi.demoteUser(userId);
      alert(`${username} demoted to user`);
      // Reload search
      const data = await adminApi.searchUsers(query);
      setUsers(data.users);
    } catch (err) {
      alert(`Failed: ${err.message}`);
    }
  };

  const handleDeactivate = async (userId, username) => {
    if (!confirm(`Deactivate "${username}"? They will be logged out and cannot log in.`)) return;

    try {
      await adminApi.deactivateUser(userId);
      alert(`${username} deactivated`);
      // Reload search
      const data = await adminApi.searchUsers(query);
      setUsers(data.users);
    } catch (err) {
      alert(`Failed: ${err.message}`);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <label className="block text-sm font-medium mb-2">Search users:</label>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type username to search..."
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {loading && <div className="text-gray-600">Loading...</div>}

      {users.length === 0 && query.length > 0 && !loading && (
        <div className="text-gray-600 text-center py-8">No users found</div>
      )}

      {users.length === 0 && query.length === 0 && (
        <div className="text-gray-600 text-center py-8">Search for users to manage roles</div>
      )}

      {users.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">Username</th>
                <th className="text-left px-4 py-2 text-sm font-semibold text-gray-700">Role</th>
                <th className="text-right px-4 py-2 text-sm font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b border-gray-100 even:bg-gray-50">
                  <td className="px-4 py-3">{user.username}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      user.role === 'owner' ? 'bg-purple-100 text-purple-800' :
                      user.role === 'admin' ? 'bg-blue-100 text-blue-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {user.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right space-x-2">
                    {user.role === 'user' && (
                      <button
                        onClick={() => handlePromote(user.id, user.username)}
                        className="px-3 py-1 rounded bg-blue-600 text-white text-sm hover:bg-blue-700 transition"
                      >
                        Promote to Admin
                      </button>
                    )}
                    {user.role === 'admin' && (
                      <>
                        <button
                          onClick={() => handleDemote(user.id, user.username)}
                          className="px-3 py-1 rounded bg-orange-600 text-white text-sm hover:bg-orange-700 transition"
                        >
                          Demote to User
                        </button>
                        <button
                          onClick={() => handleDeactivate(user.id, user.username)}
                          className="px-3 py-1 rounded bg-red-600 text-white text-sm hover:bg-red-700 transition"
                        >
                          Deactivate
                        </button>
                      </>
                    )}
                    {user.role === 'owner' && (
                      <span className="text-sm text-gray-500">Cannot modify owner</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

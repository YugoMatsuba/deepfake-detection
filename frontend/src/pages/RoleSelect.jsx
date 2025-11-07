import { useNavigate } from "react-router-dom";
import { useAuth } from "../app/useAuth.js";

export default function RoleSelect() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen fixed inset-0 grid place-items-center bg-gray-100 p-4">
      <div className="w-[min(92vw,500px)] bg-gray-200 border border-gray-300 shadow-[0_8px_24px_rgba(0,0,0,0.08)] rounded-2xl p-8">
        <header className="text-center mb-6">
          <h1 className="text-3xl font-semibold mb-2">Welcome, {user?.username}</h1>
          <p className="text-gray-700 text-sm">
            You have {user?.role === "owner" ? "owner" : "admin"} access. Choose where to go:
          </p>
        </header>

        <div className="grid gap-4">
          {/* Continue to Upload */}
          <button
            onClick={() => navigate("/upload")}
            className="w-full px-6 py-4 rounded-lg border-2 border-blue-600 bg-blue-600 text-white font-semibold hover:opacity-95 active:opacity-90 transition text-left"
          >
            <div className="text-lg font-semibold mb-1">Continue to Upload</div>
            <div className="text-sm opacity-90">Upload and analyze videos</div>
          </button>

          {/* Admin Dashboard */}
          <button
            onClick={() => navigate("/admin")}
            className="w-full px-6 py-4 rounded-lg border-2 border-gray-400 bg-white text-gray-900 font-semibold hover:bg-gray-50 active:bg-gray-100 transition text-left"
          >
            <div className="text-lg font-semibold mb-1">Admin Dashboard</div>
            <div className="text-sm text-gray-600">
              Manage users, view audit logs, and reassign analyses
            </div>
          </button>
        </div>

        <footer className="mt-6 text-center">
          <button onClick={logout} className="text-gray-700 underline text-sm hover:text-gray-900">
            Logout
          </button>
        </footer>
      </div>
    </div>
  );
}

import { useNavigate } from "react-router-dom";
import FileUploader from "./FileUploader";
import { useAuth } from "../app/useAuth.js";

export default function Page() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <main className="flex min-h-screen items-center justify-center relative">
      {/* Past Analyses button in top-left corner */}
      <button
        onClick={() => navigate("/reports")}
        className="absolute top-4 left-4 px-4 py-2 rounded-lg border border-blue-600 bg-blue-600 text-white hover:opacity-95 transition text-sm font-medium"
      >
        Past Analyses
      </button>

      {/* Logout button in top-right corner */}
      <button
        onClick={handleLogout}
        className="absolute top-4 right-4 px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 transition text-sm"
      >
        Logout
      </button>

      <FileUploader />
    </main>
  );
}

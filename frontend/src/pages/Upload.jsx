import FileUploader from "./FileUploader";
import { useAuth } from "../app/useAuth.js";

export default function Page() {
  const { logout } = useAuth();

  return (
    <main className="flex min-h-screen items-center justify-center relative">
      {/* Logout button in top-right corner */}
      <button
        onClick={logout}
        className="absolute top-4 right-4 px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 transition text-sm"
      >
        Logout
      </button>

      <FileUploader />
    </main>
  );
}

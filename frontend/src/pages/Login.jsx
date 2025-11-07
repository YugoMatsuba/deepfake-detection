import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../app/useAuth.js";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState(null);
  const [showForgotPopup, setShowForgotPopup] = useState(false);

  const navigate = useNavigate();
  const { login } = useAuth();

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr(null);
    setSubmitting(true);

    try {
      const usernameValue = username.trim();
      const data = await login(usernameValue, password);

      // Role-based routing after successful login
      if (data.user.role === "admin" || data.user.role === "owner") {
        navigate("/role-select", { replace: true });
      } else {
        navigate("/upload", { replace: true });
      }
    } catch (error) {
      // Handle specific error cases
      const errorCode = error.body?.error;

      if (errorCode === "account_pending_approval") {
        setErr("Your account is awaiting admin approval. Please check back later.");
      } else if (errorCode === "invalid_credentials") {
        setErr("Invalid username or password.");
      } else {
        setErr(error.message || "Login failed");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-[100svh] fixed inset-0 grid place-items-center bg-gray-100 p-4">
      {/* Centered square login card with grey background */}
      <div className="w-[min(92vw,420px)] aspect-square bg-gray-200 border border-gray-300 shadow-[0_8px_24px_rgba(0,0,0,0.08)] rounded-2xl p-6 flex flex-col justify-center">
        <header className="text-center mb-2">
          <h1 className="m-0 text-[32px] leading-none font-semibold">Login</h1>
        </header>

        {err && <p className="text-red-600 text-sm mb-2">{err}</p>}

        <form onSubmit={onSubmit} className="grid gap-3">
          {/* Email */}
          <div>
            <label htmlFor="username" className="block mb-1 text-[13px]">
              Username
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              required
              disabled={submitting}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="username"
              className="w-full box-border px-3 py-2 rounded-lg border border-gray-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
          </div>

          {/* Password with show/hide */}
          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="password" className="block mb-1 text-[13px]">
                Password
              </label>
              <button
                type="button"
                disabled={submitting}
                onClick={() => setShowPassword((s) => !s)}
                className="text-gray-900 underline text-xs disabled:opacity-50"
                aria-pressed={showPassword}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              disabled={submitting}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full box-border px-3 py-2 rounded-lg border border-gray-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
          </div>

          {/* Forgot password */}
          <div className="flex items-center justify-end text-[13px]">
            <button
              type="button"
              onClick={() => setShowForgotPopup(true)}
              className="text-gray-900 underline"
            >
              Forgot password?
            </button>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full box-border px-3 py-3 rounded-lg border border-blue-600 bg-blue-600 text-white font-semibold hover:opacity-95 active:opacity-90 transition disabled:opacity-50"
          >
            {submitting ? "Logging in..." : "Login"}
          </button>
        </form>

        <footer className="mt-2 text-center text-xs opacity-80">
          Don't have an account?{" "}
          <button
            type="button"
            onClick={() => navigate("/signup")}
            className="text-gray-900 underline"
          >
            Sign up
          </button>
        </footer>
      </div>

      {/* Forgot Password Popup */}
      {showForgotPopup && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setShowForgotPopup(false)}
        >
          <div
            className="relative w-[400px] max-w-[90%] bg-white rounded-lg shadow-xl p-6"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close button */}
            <button
              className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 transition"
              onClick={() => setShowForgotPopup(false)}
              aria-label="Close"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>

            {/* Content */}
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Forgot Password?</h3>
            <p className="text-sm text-gray-700 mb-4">
              Please contact an administrator to reset your password.
            </p>
            <button
              onClick={() => setShowForgotPopup(false)}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            >
              OK
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

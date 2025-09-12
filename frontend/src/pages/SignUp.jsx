import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../app/useAuth.js";

export default function SignUp() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm]   = useState("");

  const [showPassword, setShowPassword]       = useState(false);
  const [showConfirm, setShowConfirm]         = useState(false);
  const [submitting, setSubmitting]           = useState(false);
  const [err, setErr]                         = useState(null);

  const navigate = useNavigate();
  const { signup } = useAuth();

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr(null);
    setSubmitting(true);

    try {
      if (password !== confirm) {
        throw new Error("Passwords do not match");
      }
      const usernameValue = username.trim();
      await signup(usernameValue, password);
      // For now (static): pretend success and go to home or login
      navigate("/", { replace: true });
      // or: navigate("/login", { replace: true });
    } catch (error) {
      setErr(error.message || "Sign up failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-[100svh] fixed inset-0 grid place-items-center bg-gray-100 p-4">
      {/* Same card look & feel; use natural height (lots of fields) */}
      <div className="w-[min(92vw,420px)] bg-gray-200 border border-gray-300 shadow-[0_8px_24px_rgba(0,0,0,0.08)] rounded-2xl p-6 flex flex-col justify-center">
        <header className="text-center mb-2">
          <h1 className="m-0 text-[32px] leading-none font-semibold">Sign up</h1>
        </header>

        {err && <p className="text-red-600 text-sm mb-2">{err}</p>}

        <form onSubmit={onSubmit} className="grid gap-3">
          {/* Username */}
          <div>
            <label htmlFor="su-username" className="block mb-1 text-[13px]">
              Username
            </label>
            <input
              id="su-username"
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

          {/* Password */}
          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="su-password" className="block mb-1 text-[13px]">
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
              id="su-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              disabled={submitting}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full box-border px-3 py-2 rounded-lg border border-gray-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
          </div>

          {/* Confirm Password */}
          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="su-confirm" className="block mb-1 text-[13px]">
                Confirm password
              </label>
              <button
                type="button"
                disabled={submitting}
                onClick={() => setShowConfirm((s) => !s)}
                className="text-gray-900 underline text-xs disabled:opacity-50"
                aria-pressed={showConfirm}
              >
                {showConfirm ? "Hide" : "Show"}
              </button>
            </div>
            <input
              id="su-confirm"
              type={showConfirm ? "text" : "password"}
              autoComplete="new-password"
              required
              disabled={submitting}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
              className="w-full box-border px-3 py-2 rounded-lg border border-gray-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
          </div>

          <div className="flex items-center justify-between text-[13px]">
            <button
              type="button"
              onClick={() => navigate("/login")}
              className="text-gray-900 underline"
            >
              Have an account? Log in
            </button>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full box-border px-3 py-3 rounded-lg border border-blue-600 bg-blue-600 text-white font-semibold hover:opacity-95 active:opacity-90 transition disabled:opacity-50"
          >
            {submitting ? "Creating account..." : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}

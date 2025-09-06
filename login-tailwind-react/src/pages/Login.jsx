import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../app/useAuth.js";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState(null);
  
  const navigate = useNavigate();
  const { login } = useAuth();

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr(null);
    setSubmitting(true);
    
    try {
      const usernameValue = username.trim();
      await login(usernameValue, password);
      navigate("/", { replace: true });
    } catch (error) {
      setErr(error.body?.error || error.message || "Login failed");
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

          {/* Remember + Forgot */}
          <div className="flex items-center justify-between text-[13px]">
            <label className="inline-flex items-center gap-1.5">
              <input type="checkbox" className="size-4 accent-blue-600" />
              Remember me
            </label>
            <a href="#" className="text-gray-900 underline">
              Forgot password?
            </a>
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
          Don’t have an account?{" "}
          <a href="#" className="text-gray-900 underline">
            Sign up
          </a>
        </footer>
      </div>
    </div>
  );
}

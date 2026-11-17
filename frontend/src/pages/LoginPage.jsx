import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Zap,
  ShieldCheck,
  Eye,
  EyeOff,
  ArrowRight,
  Loader2,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";
import "./Auth.css";

export default function LoginPage() {
  const { login } = useAuth();

  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }

    try {
      setSubmitting(true);

      await login({
        email: email.trim(),
        password,
      });

      const destination =
        location.state?.from?.pathname || "/dashboard";

      navigate(destination, { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;

      if (Array.isArray(detail)) {
        setError(detail.map((item) => item.msg).join(", "));
      } else {
        setError(
          typeof detail === "string"
            ? detail
            : err.message || "Login failed. Please try again."
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-background-glow" />

      <section className="auth-card">

        <div className="auth-brand">
          <div className="auth-brand-icon">
            <Zap size={26} />
          </div>

          <div>
            <h1>UNDOX</h1>
            <span>WORKFLOW RECOVERY SYSTEM</span>
          </div>
        </div>

        <div className="auth-heading">
          <span className="auth-eyebrow">
            <ShieldCheck size={15} />
            SECURE WORKSPACE ACCESS
          </span>

          <h2>Welcome back.</h2>

          <p>
            Sign in to manage workflows, monitor executions
            and coordinate recovery operations.
          </p>
        </div>

        {error && (
          <div className="auth-error" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">

          <label className="auth-label" htmlFor="login-email">
            Email Address
          </label>

          <input
            id="login-email"
            className="auth-input"
            type="email"
            placeholder="you@example.com"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />

          <div className="auth-password-heading">
            <label className="auth-label" htmlFor="login-password">
              Password
            </label>
          </div>

          <div className="auth-password-wrapper">
            <input
              id="login-password"
              className="auth-input"
              type={showPassword ? "text" : "password"}
              placeholder="Enter your password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />

            <button
              type="button"
              className="auth-password-toggle"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
            </button>
          </div>

          <button
            type="submit"
            className="auth-submit-button"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <Loader2 size={18} className="auth-spinner" />
                Signing in...
              </>
            ) : (
              <>
                Sign In
                <ArrowRight size={18} />
              </>
            )}
          </button>

        </form>

        <div className="auth-divider">
          <span>NEW TO UNDOX?</span>
        </div>

        <p className="auth-switch">
          Don't have an account?
          <Link to="/register"> Create Account</Link>
        </p>

        <div className="auth-security-note">
          <ShieldCheck size={16} />
          Secure access to your workflow workspace
        </div>

      </section>

      <footer className="auth-footer">
        © 2026 UNDOX · Workflow Failure Recovery System
      </footer>

    </main>
  );
}

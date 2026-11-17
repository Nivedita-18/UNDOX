import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Zap,
  UserPlus,
  Eye,
  EyeOff,
  ArrowRight,
  Loader2,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";
import "./Auth.css";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!email.trim() || !password || !confirmPassword) {
      setError("Please fill in all fields.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      setSubmitting(true);

      await register({
        email: email.trim(),
        password,
      });

      setSuccess("Your account has been created successfully.");

      setTimeout(() => {
        navigate("/login", {
          replace: true,
          state: { registered: true },
        });
      }, 1200);
    } catch (err) {
      const detail = err.response?.data?.detail;

      if (Array.isArray(detail)) {
        setError(detail.map((item) => item.msg).join(", "));
      } else {
        setError(
          typeof detail === "string"
            ? detail
            : err.message || "Registration failed. Please try again."
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
            <UserPlus size={15} />
            CREATE YOUR WORKSPACE ACCOUNT
          </span>

          <h2>Get started.</h2>

          <p>
            Create your account to manage workflows,
            monitor executions and recover failures.
          </p>

        </div>

        {error && (
          <div className="auth-error" role="alert">
            {error}
          </div>
        )}

        {success && (
          <div className="auth-success" role="status">
            <CheckCircle2 size={17} />
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">

          <label className="auth-label" htmlFor="register-email">
            Email Address
          </label>

          <input
            id="register-email"
            className="auth-input"
            type="email"
            placeholder="you@example.com"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />

          <div className="auth-password-heading">
            <label className="auth-label" htmlFor="register-password">
              Password
            </label>
          </div>

          <div className="auth-password-wrapper">
            <input
              id="register-password"
              className="auth-input"
              type={showPassword ? "text" : "password"}
              placeholder="Create a password"
              autoComplete="new-password"
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

          <div className="auth-password-heading">
            <label className="auth-label" htmlFor="confirm-password">
              Confirm Password
            </label>
          </div>

          <div className="auth-password-wrapper">
            <input
              id="confirm-password"
              className="auth-input"
              type={showConfirmPassword ? "text" : "password"}
              placeholder="Re-enter your password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
            />

            <button
              type="button"
              className="auth-password-toggle"
              onClick={() => setShowConfirmPassword((value) => !value)}
              aria-label={
                showConfirmPassword ? "Hide password" : "Show password"
              }
            >
              {showConfirmPassword ? (
                <EyeOff size={19} />
              ) : (
                <Eye size={19} />
              )}
            </button>
          </div>

          <button
            type="submit"
            className="auth-submit-button"
            disabled={submitting || Boolean(success)}
          >
            {submitting ? (
              <>
                <Loader2 size={18} className="auth-spinner" />
                Creating account...
              </>
            ) : (
              <>
                Create Account
                <ArrowRight size={18} />
              </>
            )}
          </button>

        </form>

        <div className="auth-divider">
          <span>ALREADY REGISTERED?</span>
        </div>

        <p className="auth-switch">
          Already have an account?
          <Link to="/login"> Sign In</Link>
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

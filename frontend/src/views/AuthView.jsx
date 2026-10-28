import React, { useState } from 'react';
import { Lock, User, Mail, Shield, ArrowRight, Sparkles, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function AuthView({ onClose, onSuccess }) {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('OPERATOR');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        await register(username, email, password, role);
      } else {
        await login(username, password);
      }
      if (onSuccess) onSuccess('Successfully authenticated!');
      if (onClose) onClose();
    } catch (err) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickDemo = async (demoUsername, demoEmail, demoRole) => {
    setError(null);
    setLoading(true);
    const demoPassword = 'DemoPassword123!';

    try {
      // Attempt login first
      try {
        await login(demoUsername, demoPassword);
      } catch {
        // If user doesn't exist, register then log in
        await register(demoUsername, demoEmail, demoPassword, demoRole);
      }
      if (onSuccess) onSuccess(`Signed in as demo ${demoRole.toLowerCase()} (${demoUsername})`);
      if (onClose) onClose();
    } catch (err) {
      setError(`Demo sign-in failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '440px' }}>
        {/* Header */}
        <div style={{
          padding: '1.5rem',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700 }}>
              {isRegister ? 'Create Operator Account' : 'Sign In to UNDOX'}
            </h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
              {isRegister ? 'Register credentials to operate workflows & recovery' : 'Enter your credentials to manage failure recovery'}
            </p>
          </div>
          {onClose && (
            <button onClick={onClose} className="btn btn-secondary btn-sm" style={{ padding: '0.35rem' }}>
              <X size={18} />
            </button>
          )}
        </div>

        {/* Form Body */}
        <div style={{ padding: '1.5rem' }}>
          {error && (
            <div style={{
              background: 'var(--danger-bg)',
              border: '1px solid var(--danger-border)',
              color: '#fb7185',
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.8125rem',
              marginBottom: '1.25rem',
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Username</label>
              <div style={{ position: 'relative' }}>
                <User size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }} />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. operator_alex"
                  className="form-input"
                  style={{ paddingLeft: '2.25rem' }}
                />
              </div>
            </div>

            {isRegister && (
              <div className="form-group">
                <label className="form-label">Email Address</label>
                <div style={{ position: 'relative' }}>
                  <Mail size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }} />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="alex@company.com"
                    className="form-input"
                    style={{ paddingLeft: '2.25rem' }}
                  />
                </div>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Password</label>
              <div style={{ position: 'relative' }}>
                <Lock size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }} />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="form-input"
                  style={{ paddingLeft: '2.25rem' }}
                />
              </div>
            </div>

            {isRegister && (
              <div className="form-group">
                <label className="form-label">System Role</label>
                <div style={{ position: 'relative' }}>
                  <Shield size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }} />
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="form-select"
                    style={{ paddingLeft: '2.25rem' }}
                  >
                    <option value="OPERATOR">Operator (Trigger, Approve & Execute)</option>
                    <option value="ADMIN">Admin (Full Administrative Privileges)</option>
                    <option value="VIEWER">Viewer (Read-Only Inspection)</option>
                  </select>
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '0.75rem' }}
            >
              {loading ? (
                <div className="spinner" style={{ width: '18px', height: '18px' }} />
              ) : (
                <>
                  <span>{isRegister ? 'Register & Continue' : 'Sign In'}</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          {/* Mode Switcher */}
          <div style={{ textAlign: 'center', marginTop: '1rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            {isRegister ? 'Already have an account?' : "Don't have an account yet?"}{' '}
            <button
              type="button"
              onClick={() => {
                setIsRegister(!isRegister);
                setError(null);
              }}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--primary)',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {isRegister ? 'Sign In' : 'Register Here'}
            </button>
          </div>

          {/* Quick Demo Pre-fills */}
          <div style={{
            marginTop: '1.5rem',
            paddingTop: '1.25rem',
            borderTop: '1px solid var(--border-subtle)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
              <Sparkles size={14} color="#818cf8" />
              <span>One-Click Demo Profiles</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={() => handleQuickDemo('demo_operator', 'operator@undox.local', 'OPERATOR')}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem' }}
              >
                Operator
              </button>
              <button
                type="button"
                onClick={() => handleQuickDemo('demo_admin', 'admin@undox.local', 'ADMIN')}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem' }}
              >
                Admin
              </button>
              <button
                type="button"
                onClick={() => handleQuickDemo('demo_viewer', 'viewer@undox.local', 'VIEWER')}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem' }}
              >
                Viewer
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

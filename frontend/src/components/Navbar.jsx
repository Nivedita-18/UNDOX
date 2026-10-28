import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Workflow, 
  PlayCircle, 
  RotateCcw, 
  ShieldCheck, 
  LogOut, 
  LogIn, 
  Database,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';

export default function Navbar({ activeTab, setActiveTab, onOpenAuthModal }) {
  const { user, isAuthenticated, logout } = useAuth();
  const [dbStatus, setDbStatus] = useState({ ok: true, text: 'Online' });

  useEffect(() => {
    let interval;
    async function checkHealth() {
      try {
        const res = await api.health.dbCheck();
        if (res.status === 'ok') {
          setDbStatus({ ok: true, text: 'Connected' });
        } else {
          setDbStatus({ ok: false, text: 'Degraded' });
        }
      } catch {
        setDbStatus({ ok: false, text: 'Offline' });
      }
    }

    checkHealth();
    interval = setInterval(checkHealth, 25000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { id: 'dashboard', label: 'Summary', icon: Activity },
    { id: 'workflows', label: 'Workflows', icon: Workflow },
    { id: 'executions', label: 'Executions', icon: PlayCircle },
    { id: 'recovery', label: 'Recovery Plans', icon: RotateCcw },
    { id: 'audit', label: 'Audit History', icon: ShieldCheck },
  ];

  const getRoleBadgeClass = (role) => {
    switch (role) {
      case 'ADMIN':
        return 'badge-admin';
      case 'OPERATOR':
        return 'badge-operator';
      default:
        return 'badge-viewer';
    }
  };

  return (
    <header style={{
      borderBottom: '1px solid var(--border-subtle)',
      background: 'rgba(10, 15, 29, 0.85)',
      backdropFilter: 'blur(16px)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: '0 2rem'
    }}>
      <div style={{
        maxWidth: '1440px',
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '70px',
        gap: '1rem'
      }}>
        {/* Brand / Logo */}
        <div 
          onClick={() => setActiveTab('dashboard')}
          style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', cursor: 'pointer' }}
        >
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 15px rgba(99, 102, 241, 0.4)'
          }}>
            <RotateCcw size={20} color="#ffffff" style={{ strokeWidth: 2.5 }} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.03em', color: '#ffffff' }}>
                UNDOX
              </span>
              <span style={{ 
                fontSize: '0.6875rem', 
                background: 'rgba(99, 102, 241, 0.15)', 
                color: '#818cf8', 
                padding: '0.15rem 0.45rem', 
                borderRadius: '4px',
                fontWeight: 700,
                letterSpacing: '0.05em'
              }}>
                ENGINE
              </span>
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Workflow Failure Recovery
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.55rem 0.95rem',
                  borderRadius: 'var(--radius-md)',
                  border: 'none',
                  background: isActive ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                  color: isActive ? '#818cf8' : 'var(--text-secondary)',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                  transition: 'all 0.18s ease'
                }}
              >
                <Icon size={17} style={{ opacity: isActive ? 1 : 0.7 }} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Right Section: System Health + User Profile */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {/* Health indicator */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.35rem 0.65rem',
            borderRadius: '9999px',
            background: dbStatus.ok ? 'rgba(16, 185, 129, 0.08)' : 'rgba(244, 63, 94, 0.08)',
            border: `1px solid ${dbStatus.ok ? 'rgba(16, 185, 129, 0.2)' : 'rgba(244, 63, 94, 0.2)'}`,
            fontSize: '0.75rem',
            color: dbStatus.ok ? '#34d399' : '#fb7185'
          }}>
            <Database size={13} />
            <span style={{ fontWeight: 600 }}>{dbStatus.text}</span>
          </div>

          {/* User profile / Auth button */}
          {isAuthenticated && user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {user.username}
                </div>
                <span className={`badge ${getRoleBadgeClass(user.role)}`} style={{ padding: '0.1rem 0.4rem', fontSize: '0.6875rem' }}>
                  {user.role}
                </span>
              </div>
              <button
                onClick={logout}
                title="Sign Out"
                className="btn btn-secondary btn-sm"
                style={{ padding: '0.45rem', borderRadius: '8px' }}
              >
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenAuthModal}
              className="btn btn-primary btn-sm"
            >
              <LogIn size={15} />
              <span>Sign In</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

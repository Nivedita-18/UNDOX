import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export default function Toast({ toast, onClose }) {
  if (!toast) return null;

  const { type = 'info', message } = toast;

  const config = {
    success: {
      icon: CheckCircle2,
      border: 'rgba(16, 185, 129, 0.4)',
      bg: 'rgba(6, 78, 59, 0.9)',
      color: '#34d399',
    },
    error: {
      icon: AlertCircle,
      border: 'rgba(244, 63, 94, 0.4)',
      bg: 'rgba(136, 19, 55, 0.9)',
      color: '#fb7185',
    },
    info: {
      icon: Info,
      border: 'rgba(99, 102, 241, 0.4)',
      bg: 'rgba(30, 27, 75, 0.9)',
      color: '#818cf8',
    },
  }[type] || {
    icon: Info,
    border: 'rgba(99, 102, 241, 0.4)',
    bg: 'rgba(30, 27, 75, 0.9)',
    color: '#818cf8',
  };

  const Icon = config.icon;

  return (
    <div style={{
      position: 'fixed',
      bottom: '1.5rem',
      right: '1.5rem',
      zIndex: 200,
      background: config.bg,
      border: `1px solid ${config.border}`,
      color: '#ffffff',
      padding: '0.875rem 1.25rem',
      borderRadius: 'var(--radius-lg)',
      display: 'flex',
      alignItems: 'center',
      gap: '0.75rem',
      boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
      backdropFilter: 'blur(10px)',
      maxWidth: '420px',
      animation: 'slideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
    }}>
      <Icon size={20} color={config.color} style={{ flexShrink: 0 }} />
      <div style={{ fontSize: '0.875rem', fontWeight: 500, flex: 1 }}>{message}</div>
      <button
        onClick={onClose}
        style={{
          background: 'transparent',
          border: 'none',
          color: 'rgba(255, 255, 255, 0.6)',
          cursor: 'pointer',
          padding: '0.2rem',
          display: 'flex',
          alignItems: 'center'
        }}
      >
        <X size={16} />
      </button>
    </div>
  );
}

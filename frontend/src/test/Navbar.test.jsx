import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Navbar from '../components/Navbar';
import { AuthProvider } from '../context/AuthContext';

// Mock client
vi.mock('../api/client', () => ({
  api: {
    health: {
      dbCheck: vi.fn().mockResolvedValue({ status: 'ok' }),
    },
    auth: {
      getMe: vi.fn().mockRejectedValue(new Error('unauthenticated')),
    },
  },
}));

describe('Navbar Component', () => {
  it('renders UNDOX branding and navigation items', () => {
    const setActiveTab = vi.fn();
    render(
      <AuthProvider>
        <Navbar activeTab="dashboard" setActiveTab={setActiveTab} onOpenAuthModal={() => {}} />
      </AuthProvider>
    );

    expect(screen.getByText('UNDOX')).toBeInTheDocument();
    expect(screen.getByText('Summary')).toBeInTheDocument();
    expect(screen.getByText('Workflows')).toBeInTheDocument();
    expect(screen.getByText('Executions')).toBeInTheDocument();
    expect(screen.getByText('Recovery Plans')).toBeInTheDocument();
    expect(screen.getByText('Audit History')).toBeInTheDocument();
  });

  it('triggers tab change when clicking navigation item', () => {
    const setActiveTab = vi.fn();
    render(
      <AuthProvider>
        <Navbar activeTab="dashboard" setActiveTab={setActiveTab} onOpenAuthModal={() => {}} />
      </AuthProvider>
    );

    fireEvent.click(screen.getByText('Workflows'));
    expect(setActiveTab).toHaveBeenCalledWith('workflows');
  });
});

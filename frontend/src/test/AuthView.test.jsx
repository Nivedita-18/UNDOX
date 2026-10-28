import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AuthView from '../views/AuthView';
import { AuthProvider } from '../context/AuthContext';

vi.mock('../api/client', () => ({
  api: {
    auth: {
      login: vi.fn().mockResolvedValue({
        access_token: 'fake-jwt-token',
        user_id: '123e4567-e89b-12d3-a456-426614174000',
        username: 'test_user',
        role: 'OPERATOR',
      }),
      register: vi.fn().mockResolvedValue({}),
      getMe: vi.fn().mockResolvedValue({
        id: '123e4567-e89b-12d3-a456-426614174000',
        username: 'test_user',
        role: 'OPERATOR',
      }),
    },
  },
}));

describe('AuthView Component', () => {
  it('renders login form by default with demo shortcuts', () => {
    render(
      <AuthProvider>
        <AuthView onClose={() => {}} onSuccess={() => {}} />
      </AuthProvider>
    );

    expect(screen.getByText('Sign In to UNDOX')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('e.g. operator_alex')).toBeInTheDocument();
    expect(screen.getByText('One-Click Demo Profiles')).toBeInTheDocument();
  });

  it('toggles to registration mode with email and role fields', () => {
    render(
      <AuthProvider>
        <AuthView onClose={() => {}} onSuccess={() => {}} />
      </AuthProvider>
    );

    fireEvent.click(screen.getByText('Register Here'));
    expect(screen.getByText('Create Operator Account')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('alex@company.com')).toBeInTheDocument();
    expect(screen.getByText('System Role')).toBeInTheDocument();
  });
});

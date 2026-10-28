import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import WorkflowsView from '../views/WorkflowsView';
import { AuthProvider } from '../context/AuthContext';

vi.mock('../api/client', () => ({
  api: {
    workflows: {
      list: vi.fn().mockResolvedValue({
        items: [
          {
            id: 'wf-1111-2222',
            name: 'Order Processing Pipeline',
            status: 'ACTIVE',
            created_at: new Date().toISOString(),
            steps: [
              { step_order: 1, name: 'Validate Card' },
              { step_order: 2, name: 'Charge Payment' },
            ],
          },
        ],
        total: 1,
      }),
    },
    auth: {
      getMe: vi.fn().mockRejectedValue(new Error('unauthenticated')),
    },
  },
}));

describe('WorkflowsView Component', () => {
  it('renders workflow listing and details', async () => {
    render(
      <AuthProvider>
        <WorkflowsView onNavigate={() => {}} showToast={() => {}} />
      </AuthProvider>
    );

    expect(await screen.findByText('Order Processing Pipeline')).toBeInTheDocument();
    expect(screen.getByText('Validate Card')).toBeInTheDocument();
    expect(screen.getByText('Charge Payment')).toBeInTheDocument();
  });
});

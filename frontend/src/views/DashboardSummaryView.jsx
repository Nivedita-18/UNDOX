import React, { useState, useEffect } from 'react';
import { 
  Workflow, 
  PlayCircle, 
  AlertTriangle, 
  RotateCcw, 
  CheckCircle2, 
  ShieldAlert, 
  ArrowRight, 
  Plus, 
  Activity,
  Layers,
  Clock,
  Sparkles
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function DashboardSummaryView({ onNavigate, showToast }) {
  const { isOperator } = useAuth();
  const [stats, setStats] = useState({
    workflowsCount: 0,
    executionsCount: 0,
    failuresCount: 0,
    plansCount: 0,
    pendingApprovalsCount: 0,
    auditEventsCount: 0,
  });
  const [recentExecutions, setRecentExecutions] = useState([]);
  const [pendingPlans, setPendingPlans] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [triggeringWorkflowId, setTriggeringWorkflowId] = useState('');
  const [simulateFailure, setSimulateFailure] = useState(true);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      // 1. Fetch workflows
      const wfRes = await api.workflows.list(20, 0);
      const wfs = wfRes.items || [];
      setWorkflows(wfs);

      // 2. Fetch audit events to approximate recent activities & executions
      const auditRes = await api.audit.listEvents({ limit: 50 });
      const auditItems = auditRes.items || [];

      // Extract unique execution IDs from audit logs
      const executionIds = [
        ...new Set(
          auditItems
            .map((e) => e.execution_id)
            .filter(Boolean)
        ),
      ].slice(0, 10);

      // Fetch details for recent executions
      const execPromises = executionIds.map((id) =>
        api.executions.get(id).catch(() => null)
      );
      const execResults = (await Promise.all(execPromises)).filter(Boolean);
      setRecentExecutions(execResults);

      const failedExecs = execResults.filter((e) => e.status === 'FAILED');

      // Fetch recovery plans for failed executions
      let allPlans = [];
      for (const failed of failedExecs.slice(0, 6)) {
        try {
          const plans = await api.recovery.listPlansForExecution(failed.id);
          allPlans.push(...plans);
        } catch {
          // ignore
        }
      }

      const pending = allPlans.filter((p) => p.status === 'PENDING');
      setPendingPlans(pending);

      setStats({
        workflowsCount: wfRes.total || wfs.length,
        executionsCount: execResults.length,
        failuresCount: failedExecs.length,
        plansCount: allPlans.length,
        pendingApprovalsCount: pending.length,
        auditEventsCount: auditRes.total || auditItems.length,
      });
    } catch (err) {
      console.error('Error loading dashboard summary:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const handleQuickTrigger = async (workflowId) => {
    if (!isOperator) {
      showToast('Operator or Admin privileges are required to trigger executions', 'error');
      return;
    }

    try {
      const failureConfig = simulateFailure
        ? { fail_at_step_order: 2, error_message: 'Simulated payment gateway timeout' }
        : null;

      const newExec = await api.executions.create(workflowId, failureConfig);
      showToast(
        `Execution triggered! Status: ${newExec.status}`,
        newExec.status === 'FAILED' ? 'error' : 'success'
      );
      loadDashboardData();
    } catch (err) {
      showToast(`Trigger failed: ${err.message}`, 'error');
    }
  };

  const handleCreateSampleWorkflow = async () => {
    if (!isOperator) {
      showToast('Operator or Admin role required', 'error');
      return;
    }
    try {
      const sample = {
        name: `Order Fulfillment Pipeline ${Math.floor(Math.random() * 900 + 100)}`,
        steps: [
          { step_order: 1, name: 'Inventory Reservation', payload: { sku: 'PRO-99', qty: 2 } },
          { step_order: 2, name: 'Payment Authorization', payload: { gateway: 'Stripe', amount: 149.00 } },
          { step_order: 3, name: 'Shipping Label Generation', payload: { carrier: 'FedEx' } },
        ],
      };
      await api.workflows.create(sample);
      showToast('Sample workflow created successfully!', 'success');
      loadDashboardData();
    } catch (err) {
      showToast(`Creation failed: ${err.message}`, 'error');
    }
  };

  if (loading) {
    return (
      <div className="state-container" style={{ minHeight: '60vh' }}>
        <div className="spinner" />
        <p style={{ marginTop: '1rem', color: 'var(--text-secondary)' }}>
          Aggregating recovery metrics and system state...
        </p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '2rem' }}>
      {/* Top Banner / Heading */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '2rem',
        flexWrap: 'wrap',
        gap: '1rem',
      }}>
        <div>
          <h1 style={{ fontSize: '1.875rem', fontWeight: 800 }}>System Overview & Metrics</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem', marginTop: '0.25rem' }}>
            Live status of automated compensation, conflict detection, and operator reviews.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={loadDashboardData}
            className="btn btn-secondary"
          >
            <RotateCcw size={15} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => onNavigate('workflows')}
            className="btn btn-primary"
          >
            <Plus size={16} />
            <span>New Workflow</span>
          </button>
        </div>
      </div>

      {/* Metrics Cards Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '1.25rem',
        marginBottom: '2.5rem',
      }}>
        {/* Workflows */}
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Total Workflows</span>
            <div style={{ padding: '0.5rem', borderRadius: '10px', background: 'rgba(99, 102, 241, 0.1)', color: '#818cf8' }}>
              <Workflow size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem' }}>{stats.workflowsCount}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Registered definitions</div>
        </div>

        {/* Executions */}
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Executions Run</span>
            <div style={{ padding: '0.5rem', borderRadius: '10px', background: 'rgba(6, 182, 212, 0.1)', color: '#22d3ee' }}>
              <PlayCircle size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem' }}>{stats.executionsCount}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Tracked execution runs</div>
        </div>

        {/* Failures */}
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Detected Failures</span>
            <div style={{ padding: '0.5rem', borderRadius: '10px', background: 'rgba(244, 63, 94, 0.1)', color: '#fb7185' }}>
              <AlertTriangle size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem', color: stats.failuresCount > 0 ? '#fb7185' : 'inherit' }}>
            {stats.failuresCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Eligible for recovery</div>
        </div>

        {/* Recovery Plans */}
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Recovery Plans</span>
            <div style={{ padding: '0.5rem', borderRadius: '10px', background: 'rgba(139, 92, 246, 0.1)', color: '#c084fc' }}>
              <RotateCcw size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem' }}>{stats.plansCount}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Synthesized LIFO plans</div>
        </div>

        {/* Pending Approvals */}
        <div className="glass-panel" style={{ padding: '1.25rem', border: stats.pendingApprovalsCount > 0 ? '1px solid rgba(245, 158, 11, 0.35)' : '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Pending Review</span>
            <div style={{ padding: '0.5rem', borderRadius: '10px', background: 'rgba(245, 158, 11, 0.1)', color: '#fbbf24' }}>
              <ShieldAlert size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem', color: stats.pendingApprovalsCount > 0 ? '#fbbf24' : 'inherit' }}>
            {stats.pendingApprovalsCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Awaiting operator approval</div>
        </div>
      </div>

      {/* Two Column Layout: Quick Trigger + Pending Approvals */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem', marginBottom: '2.5rem' }}>
        {/* Quick Launch Card */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <PlayCircle size={20} color="#22d3ee" />
            <h3 style={{ fontSize: '1.125rem' }}>Simulate Workflow Execution</h3>
          </div>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
            Trigger an execution with failure simulation to test the Recovery Planning Engine and Conflict Detection.
          </p>

          {workflows.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '1.5rem' }}>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                No workflows registered yet.
              </p>
              <button onClick={handleCreateSampleWorkflow} className="btn btn-primary btn-sm">
                <Sparkles size={14} />
                <span>Create Sample Pipeline</span>
              </button>
            </div>
          ) : (
            <div>
              <div className="form-group">
                <label className="form-label">Select Workflow</label>
                <select
                  value={triggeringWorkflowId || workflows[0]?.id}
                  onChange={(e) => setTriggeringWorkflowId(e.target.value)}
                  className="form-select"
                >
                  {workflows.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name} ({w.steps?.length || 0} steps)
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
                <input
                  type="checkbox"
                  id="simulateFailure"
                  checked={simulateFailure}
                  onChange={(e) => setSimulateFailure(e.target.checked)}
                  style={{ accentColor: 'var(--primary)', width: '16px', height: '16px', cursor: 'pointer' }}
                />
                <label htmlFor="simulateFailure" style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  Inject synthetic failure at Step 2 to generate recovery scenario
                </label>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button
                  onClick={() => handleQuickTrigger(triggeringWorkflowId || workflows[0]?.id)}
                  className="btn btn-primary"
                  style={{ flex: 1 }}
                >
                  <PlayCircle size={16} />
                  <span>Execute Now</span>
                </button>
                <button
                  onClick={handleCreateSampleWorkflow}
                  className="btn btn-secondary"
                  title="Generate another sample workflow"
                >
                  <Plus size={16} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Pending Operator Approvals Card */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ShieldAlert size={20} color="#fbbf24" />
              <h3 style={{ fontSize: '1.125rem' }}>Pending Operator Reviews</h3>
            </div>
            <button
              onClick={() => onNavigate('recovery')}
              className="btn btn-ghost btn-sm"
              style={{ color: 'var(--primary)', padding: '0.25rem 0.5rem' }}
            >
              <span>View All</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {pendingPlans.length === 0 ? (
            <div className="state-container" style={{ padding: '2rem 1rem' }}>
              <CheckCircle2 size={32} color="#34d399" />
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                All clear! No recovery plans currently waiting for review.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {pendingPlans.map((plan) => (
                <div
                  key={plan.id}
                  style={{
                    background: 'rgba(15, 23, 42, 0.6)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '0.875rem 1rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                        Plan #{plan.id.slice(0, 8)}
                      </span>
                      <span className="badge badge-pending">PENDING APPROVAL</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      Failed at Step {plan.failure_step_order} • {plan.actions?.length || 0} compensation steps
                    </div>
                  </div>
                  <button
                    onClick={() => onNavigate('recovery', { selectedPlanId: plan.id })}
                    className="btn btn-secondary btn-sm"
                  >
                    <span>Review Plan</span>
                    <ArrowRight size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Executions Section */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Activity size={20} color="#818cf8" />
            <h3 style={{ fontSize: '1.125rem' }}>Recent Workflow Executions</h3>
          </div>
          <button
            onClick={() => onNavigate('executions')}
            className="btn btn-secondary btn-sm"
          >
            <span>Full History</span>
            <ArrowRight size={14} />
          </button>
        </div>

        {recentExecutions.length === 0 ? (
          <div className="state-container" style={{ padding: '2rem 1rem' }}>
            <PlayCircle size={32} />
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
              No executions found yet. Trigger one above to see live tracing.
            </p>
          </div>
        ) : (
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Execution ID</th>
                  <th>Status</th>
                  <th>Completed Steps</th>
                  <th>Error Context</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {recentExecutions.slice(0, 6).map((exec) => {
                  const completedCount = exec.steps?.filter((s) => s.status === 'COMPLETED').length || 0;
                  const totalSteps = exec.steps?.length || 0;
                  const isFailed = exec.status === 'FAILED';

                  return (
                    <tr key={exec.id}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>
                        {exec.id.slice(0, 8)}...
                      </td>
                      <td>
                        <span className={`badge badge-${exec.status.toLowerCase()}`}>
                          {exec.status === 'RUNNING' && <span className="pulse-dot" />}
                          {exec.status}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontWeight: 600 }}>{completedCount}</span>
                        <span style={{ color: 'var(--text-muted)' }}> / {totalSteps} steps</span>
                      </td>
                      <td style={{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {exec.error_message ? (
                          <span style={{ color: '#fb7185', fontSize: '0.8125rem' }}>
                            {exec.error_message}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>—</span>
                        )}
                      </td>
                      <td>
                        <button
                          onClick={() => onNavigate('executions', { selectedExecutionId: exec.id })}
                          className="btn btn-secondary btn-sm"
                        >
                          Details
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

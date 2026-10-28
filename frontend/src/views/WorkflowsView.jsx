import React, { useState, useEffect } from 'react';
import { 
  Workflow, 
  Plus, 
  PlayCircle, 
  Layers, 
  Trash2, 
  CheckCircle2, 
  X, 
  AlertCircle,
  Clock,
  Sparkles,
  ArrowRight
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function WorkflowsView({ onNavigate, showToast }) {
  const { isOperator } = useAuth();
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showExecuteModal, setShowExecuteModal] = useState(false);
  const [executingWorkflow, setExecutingWorkflow] = useState(null);

  // Create workflow form state
  const [workflowName, setWorkflowName] = useState('');
  const [steps, setSteps] = useState([
    { step_order: 1, name: 'Validate Customer Account', payload: '{"tier": "enterprise"}' },
    { step_order: 2, name: 'Reserve Warehouse Inventory', payload: '{"warehouse": "US-WEST", "qty": 5}' },
    { step_order: 3, name: 'Process Payment Capture', payload: '{"amount": 450.00, "currency": "USD"}' },
  ]);
  const [createError, setCreateError] = useState(null);
  const [creating, setCreating] = useState(false);

  // Execute form state
  const [simulateFailure, setSimulateFailure] = useState(false);
  const [failAtStep, setFailAtStep] = useState(2);
  const [errorMessage, setErrorMessage] = useState('Connection timeout to downstream inventory service');
  const [executing, setExecuting] = useState(false);

  const fetchWorkflows = async () => {
    setLoading(true);
    try {
      const res = await api.workflows.list(100, 0);
      setWorkflows(res.items || []);
    } catch (err) {
      showToast(`Failed to load workflows: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const handleAddStep = () => {
    setSteps([
      ...steps,
      {
        step_order: steps.length + 1,
        name: `Step ${steps.length + 1}`,
        payload: '{}',
      },
    ]);
  };

  const handleRemoveStep = (index) => {
    if (steps.length <= 1) return;
    const updated = steps.filter((_, i) => i !== index).map((s, idx) => ({
      ...s,
      step_order: idx + 1,
    }));
    setSteps(updated);
  };

  const handleStepChange = (index, field, value) => {
    const updated = [...steps];
    updated[index][field] = value;
    setSteps(updated);
  };

  const handleCreateWorkflow = async (e) => {
    e.preventDefault();
    if (!isOperator) {
      showToast('Operator or Admin role required', 'error');
      return;
    }
    setCreateError(null);
    setCreating(true);

    try {
      const parsedSteps = steps.map((s) => {
        let parsedPayload = null;
        if (s.payload && s.payload.trim()) {
          try {
            parsedPayload = JSON.parse(s.payload);
          } catch {
            throw new Error(`Invalid JSON in payload for Step ${s.step_order}`);
          }
        }
        return {
          step_order: s.step_order,
          name: s.name,
          payload: parsedPayload,
        };
      });

      const newWf = await api.workflows.create({
        name: workflowName,
        steps: parsedSteps,
      });

      showToast(`Workflow "${newWf.name}" registered successfully!`, 'success');
      setShowCreateModal(false);
      setWorkflowName('');
      fetchWorkflows();
    } catch (err) {
      setCreateError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleExecute = async () => {
    if (!executingWorkflow) return;
    if (!isOperator) {
      showToast('Operator or Admin role required', 'error');
      return;
    }
    setExecuting(true);
    try {
      const failureConfig = simulateFailure
        ? { fail_at_step_order: Number(failAtStep), error_message: errorMessage }
        : null;

      const result = await api.executions.create(executingWorkflow.id, failureConfig);
      showToast(
        `Execution finished with status: ${result.status}`,
        result.status === 'FAILED' ? 'error' : 'success'
      );
      setShowExecuteModal(false);
      onNavigate('executions', { selectedExecutionId: result.id });
    } catch (err) {
      showToast(`Execution trigger failed: ${err.message}`, 'error');
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '2rem' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '2rem',
        flexWrap: 'wrap',
        gap: '1rem',
      }}>
        <div>
          <h1 style={{ fontSize: '1.875rem', fontWeight: 800 }}>Workflow Management</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem', marginTop: '0.25rem' }}>
            Declare sequential workflows with compensatable steps for automated rollback and recovery.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn btn-primary"
        >
          <Plus size={16} />
          <span>Register New Workflow</span>
        </button>
      </div>

      {/* Workflow List */}
      {loading ? (
        <div className="state-container" style={{ minHeight: '40vh' }}>
          <div className="spinner" />
        </div>
      ) : workflows.length === 0 ? (
        <div className="glass-panel state-container" style={{ padding: '3.5rem' }}>
          <Workflow size={48} color="#818cf8" />
          <h3 style={{ marginTop: '1rem', fontSize: '1.25rem' }}>No Workflows Registered Yet</h3>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '420px', margin: '0.5rem auto 1.5rem' }}>
            Create your first multi-step workflow pipeline to start triggering simulated executions and observing failure recovery.
          </p>
          <button onClick={() => setShowCreateModal(true)} className="btn btn-primary">
            <Plus size={16} />
            <span>Create Workflow Pipeline</span>
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '1.5rem' }}>
          {workflows.map((wf) => (
            <div
              key={wf.id}
              className="glass-panel"
              style={{
                padding: '1.5rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <span className="badge badge-pending">{wf.status || 'ACTIVE'}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {new Date(wf.created_at).toLocaleDateString()}
                  </span>
                </div>

                <h3 style={{ fontSize: '1.1875rem', marginBottom: '0.5rem' }}>{wf.name}</h3>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: '1.25rem' }}>
                  ID: {wf.id}
                </div>

                {/* Step preview pipeline */}
                <div style={{ marginBottom: '1.5rem' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                    Steps ({wf.steps?.length || 0}):
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    {wf.steps?.slice(0, 4).map((s) => (
                      <div
                        key={s.id || s.step_order}
                        style={{
                          background: 'rgba(255, 255, 255, 0.03)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '6px',
                          padding: '0.4rem 0.65rem',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          fontSize: '0.8125rem',
                        }}
                      >
                        <span style={{
                          background: 'rgba(99, 102, 241, 0.2)',
                          color: '#818cf8',
                          width: '18px',
                          height: '18px',
                          borderRadius: '50%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '0.6875rem',
                          fontWeight: 700,
                        }}>
                          {s.step_order}
                        </span>
                        <span style={{ color: 'var(--text-secondary)' }}>{s.name}</span>
                      </div>
                    ))}
                    {(wf.steps?.length || 0) > 4 && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center' }}>
                        + {wf.steps.length - 4} more steps
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Action buttons */}
              <div style={{ display: 'flex', gap: '0.75rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '1rem' }}>
                <button
                  onClick={() => setSelectedWorkflow(wf)}
                  className="btn btn-secondary btn-sm"
                  style={{ flex: 1 }}
                >
                  Inspect
                </button>
                <button
                  onClick={() => {
                    setExecutingWorkflow(wf);
                    setShowExecuteModal(true);
                  }}
                  className="btn btn-primary btn-sm"
                  style={{ flex: 1 }}
                >
                  <PlayCircle size={15} />
                  <span>Execute</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Inspect Workflow Modal */}
      {selectedWorkflow && (
        <div className="modal-overlay" onClick={() => setSelectedWorkflow(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '640px' }}>
            <div style={{
              padding: '1.25rem 1.5rem',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <div>
                <h3 style={{ fontSize: '1.25rem' }}>{selectedWorkflow.name}</h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                  {selectedWorkflow.id}
                </span>
              </div>
              <button onClick={() => setSelectedWorkflow(null)} className="btn btn-secondary btn-sm" style={{ padding: '0.35rem' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '1.5rem', maxHeight: '70vh', overflowY: 'auto' }}>
              <h4 style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                Execution Sequence Pipeline
              </h4>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {selectedWorkflow.steps?.map((step) => (
                  <div
                    key={step.id || step.step_order}
                    style={{
                      background: 'rgba(15, 23, 42, 0.8)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      padding: '1rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                        <span style={{
                          background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
                          color: '#fff',
                          width: '24px',
                          height: '24px',
                          borderRadius: '50%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                        }}>
                          {step.step_order}
                        </span>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{step.name}</span>
                      </div>
                      <span className="badge badge-low">Step {step.step_order}</span>
                    </div>

                    {step.payload && (
                      <div style={{
                        background: 'rgba(0, 0, 0, 0.35)',
                        border: '1px solid rgba(255, 255, 255, 0.05)',
                        borderRadius: '6px',
                        padding: '0.6rem',
                        fontSize: '0.75rem',
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--text-secondary)',
                        overflowX: 'auto',
                      }}>
                        {JSON.stringify(step.payload, null, 2)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div style={{
              padding: '1rem 1.5rem',
              borderTop: '1px solid var(--border-subtle)',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '0.75rem',
            }}>
              <button onClick={() => setSelectedWorkflow(null)} className="btn btn-secondary">
                Close
              </button>
              <button
                onClick={() => {
                  setExecutingWorkflow(selectedWorkflow);
                  setSelectedWorkflow(null);
                  setShowExecuteModal(true);
                }}
                className="btn btn-primary"
              >
                <PlayCircle size={16} />
                <span>Trigger Execution</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Trigger Execution Modal */}
      {showExecuteModal && executingWorkflow && (
        <div className="modal-overlay" onClick={() => setShowExecuteModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
            <div style={{
              padding: '1.25rem 1.5rem',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <h3 style={{ fontSize: '1.25rem' }}>Execute: {executingWorkflow.name}</h3>
              <button onClick={() => setShowExecuteModal(false)} className="btn btn-secondary btn-sm" style={{ padding: '0.35rem' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '1.5rem' }}>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
                You can trigger a normal completion run, or inject a simulated failure to verify automated recovery synthesis.
              </p>

              <div style={{
                background: 'rgba(15, 23, 42, 0.7)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                marginBottom: '1.25rem',
              }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', cursor: 'pointer', fontWeight: 600 }}>
                  <input
                    type="checkbox"
                    checked={simulateFailure}
                    onChange={(e) => setSimulateFailure(e.target.checked)}
                    style={{ accentColor: 'var(--danger)', width: '18px', height: '18px' }}
                  />
                  <span>Simulate Failure at a Step</span>
                </label>

                {simulateFailure && (
                  <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">Fail at Step Order</label>
                      <select
                        value={failAtStep}
                        onChange={(e) => setFailAtStep(e.target.value)}
                        className="form-select"
                      >
                        {executingWorkflow.steps?.map((s) => (
                          <option key={s.step_order} value={s.step_order}>
                            Step {s.step_order}: {s.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">Simulated Error Context</label>
                      <input
                        type="text"
                        value={errorMessage}
                        onChange={(e) => setErrorMessage(e.target.value)}
                        className="form-input"
                      />
                    </div>
                  </div>
                )}
              </div>

              {!isOperator && (
                <div style={{
                  background: 'var(--warning-bg)',
                  border: '1px solid var(--warning-border)',
                  color: '#fbbf24',
                  padding: '0.75rem',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.8125rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  marginBottom: '1rem',
                }}>
                  <AlertCircle size={16} />
                  <span>Operator or Admin role required to trigger executions.</span>
                </div>
              )}

              <button
                onClick={handleExecute}
                disabled={executing || !isOperator}
                className={`btn ${simulateFailure ? 'btn-danger' : 'btn-primary'}`}
                style={{ width: '100%' }}
              >
                {executing ? (
                  <div className="spinner" style={{ width: '18px', height: '18px' }} />
                ) : (
                  <>
                    <PlayCircle size={16} />
                    <span>{simulateFailure ? 'Trigger & Simulate Failure' : 'Run Workflow Execution'}</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Workflow Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '640px' }}>
            <div style={{
              padding: '1.25rem 1.5rem',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <h3 style={{ fontSize: '1.25rem' }}>Register New Workflow</h3>
              <button onClick={() => setShowCreateModal(false)} className="btn btn-secondary btn-sm" style={{ padding: '0.35rem' }}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateWorkflow} style={{ padding: '1.5rem', maxHeight: '75vh', overflowY: 'auto' }}>
              {createError && (
                <div style={{
                  background: 'var(--danger-bg)',
                  border: '1px solid var(--danger-border)',
                  color: '#fb7185',
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.8125rem',
                  marginBottom: '1.25rem',
                }}>
                  {createError}
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Workflow Name</label>
                <input
                  type="text"
                  required
                  value={workflowName}
                  onChange={(e) => setWorkflowName(e.target.value)}
                  placeholder="e.g. Multi-Cloud Provisioning Flow"
                  className="form-input"
                />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <label className="form-label" style={{ marginBottom: 0 }}>Workflow Steps ({steps.length})</label>
                  <button
                    type="button"
                    onClick={handleAddStep}
                    className="btn btn-secondary btn-sm"
                  >
                    <Plus size={14} />
                    <span>Add Step</span>
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {steps.map((s, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: 'rgba(15, 23, 42, 0.6)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-md)',
                        padding: '0.875rem',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                        <span style={{
                          background: 'rgba(99, 102, 241, 0.2)',
                          color: '#818cf8',
                          width: '22px',
                          height: '22px',
                          borderRadius: '50%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                        }}>
                          {s.step_order}
                        </span>
                        <input
                          type="text"
                          required
                          value={s.name}
                          onChange={(e) => handleStepChange(idx, 'name', e.target.value)}
                          placeholder="Step Name"
                          className="form-input"
                          style={{ flex: 1, padding: '0.45rem 0.65rem' }}
                        />
                        {steps.length > 1 && (
                          <button
                            type="button"
                            onClick={() => handleRemoveStep(idx)}
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '0.45rem', color: '#fb7185' }}
                          >
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>

                      <input
                        type="text"
                        value={s.payload}
                        onChange={(e) => handleStepChange(idx, 'payload', e.target.value)}
                        placeholder='JSON payload e.g. {"service": "s3"}'
                        className="form-input"
                        style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', padding: '0.4rem 0.65rem' }}
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !isOperator}
                  className="btn btn-primary"
                >
                  {creating ? (
                    <div className="spinner" style={{ width: '18px', height: '18px' }} />
                  ) : (
                    <span>Register Workflow</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

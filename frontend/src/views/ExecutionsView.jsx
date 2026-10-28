import React, { useState, useEffect } from 'react';
import { 
  PlayCircle, 
  RotateCcw, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  ArrowRight, 
  ShieldCheck, 
  Layers,
  ChevronRight,
  Info,
  X
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function ExecutionsView({ initialExecutionId, onNavigate, showToast }) {
  const { isOperator } = useAuth();
  const [executions, setExecutions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedExecution, setSelectedExecution] = useState(null);
  const [associatedPlans, setAssociatedPlans] = useState([]);
  const [executionAudits, setExecutionAudits] = useState([]);
  const [generatingPlan, setGeneratingPlan] = useState(false);

  const fetchExecutions = async () => {
    setLoading(true);
    try {
      // Find executions through audit events
      const auditRes = await api.audit.listEvents({ limit: 100 });
      const execIds = [
        ...new Set(
          (auditRes.items || [])
            .map((e) => e.execution_id)
            .filter(Boolean)
        ),
      ];

      const promises = execIds.map((id) => api.executions.get(id).catch(() => null));
      const loaded = (await Promise.all(promises)).filter(Boolean);
      setExecutions(loaded);

      if (initialExecutionId) {
        const found = loaded.find((e) => e.id === initialExecutionId);
        if (found) {
          selectExecutionDetails(found);
        } else {
          api.executions.get(initialExecutionId).then(selectExecutionDetails).catch(() => {});
        }
      } else if (loaded.length > 0 && !selectedExecution) {
        selectExecutionDetails(loaded[0]);
      }
    } catch (err) {
      showToast(`Failed to load executions: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const selectExecutionDetails = async (exec) => {
    setSelectedExecution(exec);
    try {
      // Fetch associated plans
      const plans = await api.recovery.listPlansForExecution(exec.id).catch(() => []);
      setAssociatedPlans(plans);

      // Fetch execution audit events
      const audits = await api.audit.getEventsForExecution(exec.id).catch(() => []);
      setExecutionAudits(audits);
    } catch {
      setAssociatedPlans([]);
      setExecutionAudits([]);
    }
  };

  useEffect(() => {
    fetchExecutions();
  }, [initialExecutionId]);

  const handleGenerateRecoveryPlan = async () => {
    if (!selectedExecution) return;
    if (!isOperator) {
      showToast('Operator or Admin role required to create recovery plans', 'error');
      return;
    }

    setGeneratingPlan(true);
    try {
      const plan = await api.recovery.createPlan(selectedExecution.id, {
        notes: `Automated recovery plan synthesized for failed execution ${selectedExecution.id}`,
      });
      showToast('Recovery plan successfully generated!', 'success');
      setAssociatedPlans([plan, ...associatedPlans]);
      onNavigate('recovery', { selectedPlanId: plan.id });
    } catch (err) {
      showToast(`Recovery plan generation failed: ${err.message}`, 'error');
    } finally {
      setGeneratingPlan(false);
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
          <h1 style={{ fontSize: '1.875rem', fontWeight: 800 }}>Execution Traces & Diagnostics</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem', marginTop: '0.25rem' }}>
            Inspect step-by-step telemetry, pinpoint failure boundaries, and synthesize compensation plans.
          </p>
        </div>
        <button onClick={fetchExecutions} className="btn btn-secondary">
          <RotateCcw size={15} />
          <span>Refresh</span>
        </button>
      </div>

      {loading ? (
        <div className="state-container" style={{ minHeight: '40vh' }}>
          <div className="spinner" />
        </div>
      ) : executions.length === 0 ? (
        <div className="glass-panel state-container" style={{ padding: '3.5rem' }}>
          <PlayCircle size={48} color="#22d3ee" />
          <h3 style={{ marginTop: '1rem', fontSize: '1.25rem' }}>No Execution Traces Recorded</h3>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '420px', margin: '0.5rem auto 1.5rem' }}>
            Trigger an execution from the Workflows tab to begin collecting diagnostic timelines.
          </p>
          <button onClick={() => onNavigate('workflows')} className="btn btn-primary">
            <span>Go to Workflows</span>
            <ArrowRight size={16} />
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 1fr) minmax(460px, 1.8fr)', gap: '1.5rem' }}>
          {/* Left: Execution List */}
          <div className="glass-panel" style={{ padding: '1rem', maxHeight: '80vh', overflowY: 'auto' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, padding: '0.5rem 0.5rem 0.75rem', borderBottom: '1px solid var(--border-subtle)' }}>
              Execution History ({executions.length})
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.75rem' }}>
              {executions.map((exec) => {
                const isSelected = selectedExecution?.id === exec.id;
                const completedSteps = exec.steps?.filter((s) => s.status === 'COMPLETED').length || 0;
                const totalSteps = exec.steps?.length || 0;

                return (
                  <div
                    key={exec.id}
                    onClick={() => selectExecutionDetails(exec)}
                    style={{
                      padding: '0.875rem 1rem',
                      borderRadius: 'var(--radius-md)',
                      background: isSelected ? 'rgba(99, 102, 241, 0.15)' : 'rgba(15, 23, 42, 0.4)',
                      border: isSelected ? '1px solid #6366f1' : '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                      <span className={`badge badge-${exec.status.toLowerCase()}`}>
                        {exec.status === 'RUNNING' && <span className="pulse-dot" />}
                        {exec.status}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {exec.started_at ? new Date(exec.started_at).toLocaleTimeString() : ''}
                      </span>
                    </div>

                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: '0.35rem' }}>
                      {exec.id}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>
                        {completedSteps} / {totalSteps} steps completed
                      </span>
                      <ChevronRight size={16} color={isSelected ? '#818cf8' : 'var(--text-muted)'} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: Selected Execution Details */}
          {selectedExecution && (
            <div className="glass-panel" style={{ padding: '1.75rem', maxHeight: '80vh', overflowY: 'auto' }}>
              {/* Execution Summary Header */}
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
                    <span className={`badge badge-${selectedExecution.status.toLowerCase()}`} style={{ fontSize: '0.8125rem', padding: '0.3rem 0.75rem' }}>
                      {selectedExecution.status}
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', color: 'var(--text-dim)' }}>
                      {selectedExecution.id}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Started: {selectedExecution.started_at ? new Date(selectedExecution.started_at).toLocaleString() : 'N/A'}
                    {selectedExecution.completed_at && ` • Completed: ${new Date(selectedExecution.completed_at).toLocaleString()}`}
                  </div>
                </div>

                {/* Plan Generation Button */}
                {selectedExecution.status === 'FAILED' && (
                  <button
                    onClick={handleGenerateRecoveryPlan}
                    disabled={generatingPlan || !isOperator}
                    className="btn btn-primary"
                  >
                    {generatingPlan ? (
                      <div className="spinner" style={{ width: '16px', height: '16px' }} />
                    ) : (
                      <>
                        <RotateCcw size={16} />
                        <span>Synthesize Recovery Plan</span>
                      </>
                    )}
                  </button>
                )}
              </div>

              {/* Error Box if Failed */}
              {selectedExecution.error_message && (
                <div style={{
                  background: 'var(--danger-bg)',
                  border: '1px solid var(--danger-border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '1rem',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.75rem',
                  marginBottom: '1.75rem',
                }}>
                  <AlertTriangle size={20} color="#fb7185" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <div style={{ fontSize: '0.875rem', fontWeight: 700, color: '#fb7185' }}>
                      Execution Failure Boundary Reached
                    </div>
                    <div style={{ fontSize: '0.8125rem', color: '#fecdd3', marginTop: '0.25rem', fontFamily: 'var(--font-mono)' }}>
                      {selectedExecution.error_message}
                    </div>
                  </div>
                </div>
              )}

              {/* Step Sequence Timeline */}
              <div style={{ marginBottom: '2rem' }}>
                <h4 style={{ fontSize: '0.9375rem', fontWeight: 700, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Layers size={17} color="#818cf8" />
                  <span>Execution Step Sequence</span>
                </h4>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {selectedExecution.steps?.map((step) => {
                    const isSuccess = step.status === 'COMPLETED';
                    const isFailed = step.status === 'FAILED';

                    return (
                      <div
                        key={step.id || step.step_order}
                        style={{
                          background: 'rgba(15, 23, 42, 0.65)',
                          border: isFailed
                            ? '1px solid rgba(244, 63, 94, 0.4)'
                            : isSuccess
                            ? '1px solid rgba(16, 185, 129, 0.25)'
                            : '1px solid var(--border-subtle)',
                          borderRadius: 'var(--radius-md)',
                          padding: '1rem',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                            <span style={{
                              background: isFailed ? '#f43f5e' : isSuccess ? '#10b981' : 'rgba(255, 255, 255, 0.1)',
                              color: '#fff',
                              width: '22px',
                              height: '22px',
                              borderRadius: '50%',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                            }}>
                              {step.step_order}
                            </span>
                            <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.875rem' }}>
                              {step.name}
                            </span>
                          </div>
                          <span className={`badge badge-${step.status.toLowerCase()}`}>
                            {step.status}
                          </span>
                        </div>

                        {step.error_message && (
                          <div style={{
                            fontSize: '0.75rem',
                            color: '#fb7185',
                            background: 'rgba(244, 63, 94, 0.1)',
                            padding: '0.4rem 0.65rem',
                            borderRadius: '4px',
                            marginTop: '0.5rem',
                            fontFamily: 'var(--font-mono)',
                          }}>
                            {step.error_message}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Associated Recovery Plans */}
              {associatedPlans.length > 0 && (
                <div style={{ marginBottom: '2rem' }}>
                  <h4 style={{ fontSize: '0.9375rem', fontWeight: 700, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <RotateCcw size={17} color="#c084fc" />
                    <span>Synthesized Recovery Plans ({associatedPlans.length})</span>
                  </h4>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {associatedPlans.map((plan) => (
                      <div
                        key={plan.id}
                        style={{
                          background: 'rgba(15, 23, 42, 0.8)',
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
                            <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>
                              Plan #{plan.id.slice(0, 8)}
                            </span>
                            <span className={`badge badge-${plan.status.toLowerCase()}`}>
                              {plan.status}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                            {plan.actions?.length || 0} compensation actions
                          </div>
                        </div>

                        <button
                          onClick={() => onNavigate('recovery', { selectedPlanId: plan.id })}
                          className="btn btn-secondary btn-sm"
                        >
                          <span>Inspect Plan</span>
                          <ArrowRight size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Execution Audit Trail */}
              {executionAudits.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.9375rem', fontWeight: 700, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <ShieldCheck size={17} color="#34d399" />
                    <span>Audit Trail for this Execution</span>
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    {executionAudits.slice(0, 5).map((ev) => (
                      <div
                        key={ev.id}
                        style={{
                          background: 'rgba(255, 255, 255, 0.02)',
                          padding: '0.5rem 0.75rem',
                          borderRadius: '6px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: '0.75rem',
                        }}
                      >
                        <div>
                          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{ev.event_type}</span>
                          <span style={{ color: 'var(--text-muted)', marginLeft: '0.5rem' }}>{ev.message}</span>
                        </div>
                        <span className={`badge badge-${ev.outcome.toLowerCase()}`} style={{ fontSize: '0.6875rem' }}>
                          {ev.outcome}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

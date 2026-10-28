import React, { useState, useEffect } from 'react';
import { 
  RotateCcw, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle, 
  PlayCircle, 
  ShieldAlert, 
  ShieldCheck, 
  Layers, 
  Clock, 
  ChevronRight,
  Info,
  X,
  Lock,
  ArrowRight
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function RecoveryPlansView({ initialPlanId, onNavigate, showToast }) {
  const { isOperator, canApprove, canExecute, user } = useAuth();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [conflictsReport, setConflictsReport] = useState(null);
  const [conflictsLoading, setConflictsLoading] = useState(false);

  // Modals
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showExecuteModal, setShowExecuteModal] = useState(false);

  // Form states
  const [approveReason, setApproveReason] = useState('Verified rollback steps and compensations');
  const [allowManualReview, setAllowManualReview] = useState(false);
  const [allowIrreversible, setAllowIrreversible] = useState(false);

  const [rejectReason, setRejectReason] = useState('');
  const [submittingAction, setSubmittingAction] = useState(false);

  // Recovery execution simulation options
  const [simulateExecFailure, setSimulateExecFailure] = useState(false);
  const [failAtActionOrder, setFailAtActionOrder] = useState(1);
  const [execErrorMessage, setExecErrorMessage] = useState('Downstream compensation timeout');

  const fetchPlans = async () => {
    setLoading(true);
    try {
      // Find plans through audit logs or executions
      const auditRes = await api.audit.listEvents({ limit: 100 });
      const planIds = [
        ...new Set(
          (auditRes.items || [])
            .map((e) => e.recovery_plan_id)
            .filter(Boolean)
        ),
      ];

      const promises = planIds.map((id) => api.recovery.getPlan(id).catch(() => null));
      const loaded = (await Promise.all(promises)).filter(Boolean);
      setPlans(loaded);

      if (initialPlanId) {
        const found = loaded.find((p) => p.id === initialPlanId);
        if (found) {
          selectPlanDetails(found);
        } else {
          api.recovery.getPlan(initialPlanId).then(selectPlanDetails).catch(() => {});
        }
      } else if (loaded.length > 0 && !selectedPlan) {
        selectPlanDetails(loaded[0]);
      }
    } catch (err) {
      showToast(`Failed to load recovery plans: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const selectPlanDetails = async (plan) => {
    setSelectedPlan(plan);
    setConflictsLoading(true);
    try {
      const conflicts = await api.recovery.getConflicts(plan.id);
      setConflictsReport(conflicts);
    } catch (err) {
      console.warn('Conflict detection query failed:', err);
      setConflictsReport(null);
    } finally {
      setConflictsLoading(false);
    }
  };

  useEffect(() => {
    fetchPlans();
  }, [initialPlanId]);

  const handleApprove = async () => {
    if (!selectedPlan) return;
    if (!canApprove) {
      showToast('Operator or Admin role required to approve plans', 'error');
      return;
    }
    setSubmittingAction(true);
    try {
      const updated = await api.recovery.approvePlan(selectedPlan.id, {
        reason: approveReason,
        allow_manual_review_actions: allowManualReview,
        allow_irreversible_actions: allowIrreversible,
      });
      showToast(`Plan approved successfully by ${user?.username || 'operator'}!`, 'success');
      setShowApproveModal(false);
      setSelectedPlan(updated);
      fetchPlans();
    } catch (err) {
      showToast(`Approval failed: ${err.message}`, 'error');
    } finally {
      setSubmittingAction(false);
    }
  };

  const handleReject = async () => {
    if (!selectedPlan) return;
    if (!canApprove) {
      showToast('Operator or Admin role required to reject plans', 'error');
      return;
    }
    if (!rejectReason.trim()) {
      showToast('Please provide a mandatory rejection reason', 'error');
      return;
    }
    setSubmittingAction(true);
    try {
      const updated = await api.recovery.rejectPlan(selectedPlan.id, rejectReason);
      showToast('Recovery plan rejected and recorded in audit log', 'info');
      setShowRejectModal(false);
      setSelectedPlan(updated);
      fetchPlans();
    } catch (err) {
      showToast(`Rejection failed: ${err.message}`, 'error');
    } finally {
      setSubmittingAction(false);
    }
  };

  const handleExecute = async () => {
    if (!selectedPlan) return;
    if (!canExecute) {
      showToast('Operator or Admin role required to execute plans', 'error');
      return;
    }
    setSubmittingAction(true);
    try {
      const payload = {
        allow_manual_review_actions: true,
        allow_irreversible_actions: true,
      };
      if (simulateExecFailure) {
        payload.failure_simulation = {
          fail_at_action_order: Number(failAtActionOrder),
          error_message: execErrorMessage,
        };
      }

      const result = await api.recovery.executePlan(selectedPlan.id, payload);
      showToast(
        `Recovery execution completed with status: ${result.status}`,
        result.status === 'COMPLETED' ? 'success' : 'error'
      );
      setShowExecuteModal(false);
      const updatedPlan = await api.recovery.getPlan(selectedPlan.id);
      setSelectedPlan(updatedPlan);
      fetchPlans();
    } catch (err) {
      showToast(`Execution failed: ${err.message}`, 'error');
    } finally {
      setSubmittingAction(false);
    }
  };

  const getSeverityBadgeClass = (severity) => {
    switch (severity?.toUpperCase()) {
      case 'HIGH':
        return 'badge-high';
      case 'MEDIUM':
        return 'badge-medium';
      default:
        return 'badge-low';
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
          <h1 style={{ fontSize: '1.875rem', fontWeight: 800 }}>Recovery Planning & Conflict Engine</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem', marginTop: '0.25rem' }}>
            Inspect reverse-ordered compensation sequences, analyze blocking state conflicts, and enforce operator approvals.
          </p>
        </div>
        <button onClick={fetchPlans} className="btn btn-secondary">
          <RotateCcw size={15} />
          <span>Refresh</span>
        </button>
      </div>

      {loading ? (
        <div className="state-container" style={{ minHeight: '40vh' }}>
          <div className="spinner" />
        </div>
      ) : plans.length === 0 ? (
        <div className="glass-panel state-container" style={{ padding: '3.5rem' }}>
          <RotateCcw size={48} color="#c084fc" />
          <h3 style={{ marginTop: '1rem', fontSize: '1.25rem' }}>No Recovery Plans Generated Yet</h3>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '420px', margin: '0.5rem auto 1.5rem' }}>
            Trigger a workflow with simulated failure, then click "Synthesize Recovery Plan" from the Executions tab.
          </p>
          <button onClick={() => onNavigate('executions')} className="btn btn-primary">
            <span>View Executions</span>
            <ArrowRight size={16} />
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 1fr) minmax(500px, 1.8fr)', gap: '1.5rem' }}>
          {/* Left: Plans List */}
          <div className="glass-panel" style={{ padding: '1rem', maxHeight: '80vh', overflowY: 'auto' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, padding: '0.5rem 0.5rem 0.75rem', borderBottom: '1px solid var(--border-subtle)' }}>
              Recovery Plans ({plans.length})
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.75rem' }}>
              {plans.map((p) => {
                const isSelected = selectedPlan?.id === p.id;
                return (
                  <div
                    key={p.id}
                    onClick={() => selectPlanDetails(p)}
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
                      <span className={`badge badge-${p.status.toLowerCase()}`}>
                        {p.status}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {p.created_at ? new Date(p.created_at).toLocaleTimeString() : ''}
                      </span>
                    </div>

                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: '0.35rem' }}>
                      Plan #{p.id.slice(0, 8)}...
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>
                        {p.actions?.length || 0} compensation actions
                      </span>
                      <ChevronRight size={16} color={isSelected ? '#818cf8' : 'var(--text-muted)'} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: Selected Plan Inspector */}
          {selectedPlan && (
            <div className="glass-panel" style={{ padding: '1.75rem', maxHeight: '80vh', overflowY: 'auto' }}>
              {/* Header and Status */}
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
                    <span className={`badge badge-${selectedPlan.status.toLowerCase()}`} style={{ fontSize: '0.8125rem', padding: '0.3rem 0.75rem' }}>
                      {selectedPlan.status}
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', color: 'var(--text-dim)' }}>
                      ID: {selectedPlan.id}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Failed at Step {selectedPlan.failure_step_order} • Created: {new Date(selectedPlan.created_at).toLocaleString()}
                  </div>
                </div>

                {/* Operator Actions (Approve / Reject / Execute) */}
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {selectedPlan.status === 'PENDING' && (
                    <>
                      <button
                        onClick={() => setShowApproveModal(true)}
                        disabled={!canApprove}
                        className="btn btn-success btn-sm"
                        title={!canApprove ? 'Operator or Admin role required' : ''}
                      >
                        <CheckCircle2 size={15} />
                        <span>Approve Plan</span>
                      </button>
                      <button
                        onClick={() => setShowRejectModal(true)}
                        disabled={!canApprove}
                        className="btn btn-danger btn-sm"
                        title={!canApprove ? 'Operator or Admin role required' : ''}
                      >
                        <XCircle size={15} />
                        <span>Reject Plan</span>
                      </button>
                    </>
                  )}

                  {selectedPlan.status === 'APPROVED' && (
                    <button
                      onClick={() => setShowExecuteModal(true)}
                      disabled={!canExecute}
                      className="btn btn-primary btn-sm"
                      title={!canExecute ? 'Operator or Admin role required' : ''}
                    >
                      <PlayCircle size={15} />
                      <span>Execute Recovery</span>
                    </button>
                  )}
                </div>
              </div>

              {/* RBAC Notice if Viewer */}
              {!isOperator && (
                <div style={{
                  background: 'rgba(148, 163, 184, 0.1)',
                  border: '1px solid rgba(148, 163, 184, 0.25)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.75rem 1rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.8125rem',
                  color: '#cbd5e1',
                  marginBottom: '1.5rem',
                }}>
                  <Lock size={16} />
                  <span>You are signed in with read-only VIEWER privileges. Operator or Admin role is required to approve or execute recovery.</span>
                </div>
              )}

              {/* Operator Decision Notice if already Approved/Rejected */}
              {selectedPlan.decision_operator && (
                <div style={{
                  background: selectedPlan.status === 'APPROVED' ? 'var(--success-bg)' : 'var(--danger-bg)',
                  border: `1px solid ${selectedPlan.status === 'APPROVED' ? 'var(--success-border)' : 'var(--danger-border)'}`,
                  borderRadius: 'var(--radius-md)',
                  padding: '0.875rem 1rem',
                  marginBottom: '1.5rem',
                  fontSize: '0.8125rem',
                }}>
                  <div style={{ fontWeight: 700, color: selectedPlan.status === 'APPROVED' ? '#34d399' : '#fb7185' }}>
                    Operator Decision: {selectedPlan.status} by @{selectedPlan.decision_operator}
                  </div>
                  <div style={{ color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                    Reason: "{selectedPlan.decision_reason || 'No comment provided'}"
                  </div>
                </div>
              )}

              {/* Conflict Detection Engine Card */}
              <div style={{
                background: 'rgba(15, 23, 42, 0.75)',
                border: conflictsReport?.has_conflicts || conflictsReport?.is_stale
                  ? '1px solid rgba(245, 158, 11, 0.4)'
                  : '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-lg)',
                padding: '1.25rem',
                marginBottom: '1.75rem',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <ShieldAlert size={18} color="#f59e0b" />
                    <h4 style={{ fontSize: '0.9375rem', fontWeight: 700 }}>Conflict Detection Engine</h4>
                  </div>
                  {conflictsLoading ? (
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Scanning state...</span>
                  ) : (
                    <span className={`badge ${conflictsReport?.has_conflicts ? 'badge-medium' : 'badge-completed'}`}>
                      {conflictsReport?.has_conflicts ? 'Conflicts Detected' : 'Zero State Conflicts'}
                    </span>
                  )}
                </div>

                {conflictsReport?.is_stale && (
                  <div style={{
                    background: 'var(--danger-bg)',
                    border: '1px solid var(--danger-border)',
                    color: '#fb7185',
                    padding: '0.6rem 0.85rem',
                    borderRadius: '6px',
                    fontSize: '0.8125rem',
                    marginBottom: '0.75rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                  }}>
                    <AlertTriangle size={15} />
                    <span>Warning: Recovery plan is STALE because execution state has changed since generation.</span>
                  </div>
                )}

                {conflictsReport?.conflicts && conflictsReport.conflicts.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {conflictsReport.conflicts.map((c, i) => (
                      <div
                        key={i}
                        style={{
                          background: 'rgba(0, 0, 0, 0.25)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '6px',
                          padding: '0.65rem 0.85rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '0.5rem',
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <span className={`badge ${getSeverityBadgeClass(c.severity)}`} style={{ fontSize: '0.6875rem' }}>
                              {c.severity}
                            </span>
                            <span style={{ fontWeight: 600, fontSize: '0.8125rem', color: 'var(--text-primary)' }}>
                              {c.conflict_type}
                            </span>
                            {c.is_blocking && (
                              <span className="badge badge-high" style={{ fontSize: '0.625rem' }}>BLOCKING</span>
                            )}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                            {c.reason}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    No conflicting resource dependencies or stale step targets detected.
                  </p>
                )}
              </div>

              {/* Action Sequence List */}
              <div>
                <h4 style={{ fontSize: '0.9375rem', fontWeight: 700, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Layers size={17} color="#818cf8" />
                  <span>Ordered Compensation Sequence ({selectedPlan.actions?.length || 0})</span>
                </h4>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {selectedPlan.actions?.map((act) => (
                    <div
                      key={act.id || act.action_order}
                      style={{
                        background: 'rgba(15, 23, 42, 0.65)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-md)',
                        padding: '1rem',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                          <span style={{
                            background: 'rgba(139, 92, 246, 0.2)',
                            color: '#c084fc',
                            width: '24px',
                            height: '24px',
                            borderRadius: '50%',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                          }}>
                            {act.action_order}
                          </span>
                          <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.875rem' }}>
                            {act.action_type}
                          </span>
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
                            Target: Step {act.target_step_order} ({act.target_step_name})
                          </span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          {act.requires_manual_review && (
                            <span className="badge badge-medium" style={{ fontSize: '0.6875rem' }}>
                              MANUAL REVIEW
                            </span>
                          )}
                          {act.is_irreversible && (
                            <span className="badge badge-high" style={{ fontSize: '0.6875rem' }}>
                              IRREVERSIBLE
                            </span>
                          )}
                          <span className={`badge badge-${act.status.toLowerCase()}`}>
                            {act.status}
                          </span>
                        </div>
                      </div>

                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                        {act.description}
                      </div>

                      {act.execution_result && (
                        <div style={{
                          background: 'rgba(0, 0, 0, 0.35)',
                          border: '1px solid rgba(255, 255, 255, 0.05)',
                          borderRadius: '6px',
                          padding: '0.5rem 0.75rem',
                          fontSize: '0.75rem',
                          fontFamily: 'var(--font-mono)',
                          color: '#34d399',
                          marginTop: '0.5rem',
                        }}>
                          Result: {JSON.stringify(act.execution_result)}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Approve Plan Modal */}
      {showApproveModal && selectedPlan && (
        <div className="modal-overlay" onClick={() => setShowApproveModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
            <div style={{
              padding: '1.25rem 1.5rem',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <h3 style={{ fontSize: '1.25rem' }}>Approve Recovery Plan</h3>
              <button onClick={() => setShowApproveModal(false)} className="btn btn-secondary btn-sm" style={{ padding: '0.35rem' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '1.5rem' }}>
              <div className="form-group">
                <label className="form-label">Approval Justification / Reason</label>
                <textarea
                  rows={3}
                  value={approveReason}
                  onChange={(e) => setApproveReason(e.target.value)}
                  className="form-textarea"
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', margin: '1.25rem 0' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={allowManualReview}
                    onChange={(e) => setAllowManualReview(e.target.checked)}
                    style={{ accentColor: 'var(--primary)', width: '16px', height: '16px' }}
                  />
                  <span>Explicitly permit actions flagged as requiring manual review</span>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={allowIrreversible}
                    onChange={(e) => setAllowIrreversible(e.target.checked)}
                    style={{ accentColor: 'var(--danger)', width: '16px', height: '16px' }}
                  />
                  <span>Consent to actions marked as irreversible</span>
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button onClick={() => setShowApproveModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button onClick={handleApprove} disabled={submittingAction} className="btn btn-success">
                  {submittingAction ? (
                    <div className="spinner" style={{ width: '18px', height: '18px' }} />
                  ) : (
                    <span>Confirm Approval</span>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reject Plan Modal */}
      {showRejectModal && selectedPlan && (
        <div className="modal-overlay" onClick={() => setShowRejectModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
            <div style={{
              padding: '1.25rem 1.5rem',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <h3 style={{ fontSize: '1.25rem' }}>Reject Recovery Plan</h3>
              <button onClick={() => setShowRejectModal(false)} className="btn btn-secondary btn-sm" style={{ padding: '0.35rem' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '1.5rem' }}>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                Rejected plans cannot be executed. You must provide a clear audit reason for this rejection.
              </p>

              <div className="form-group">
                <label className="form-label">Mandatory Rejection Reason</label>
                <textarea
                  rows={3}
                  required
                  placeholder="e.g. Unresolved data conflict with external warehouse state"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  className="form-textarea"
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button onClick={() => setShowRejectModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button onClick={handleReject} disabled={submittingAction || !rejectReason.trim()} className="btn btn-danger">
                  {submittingAction ? (
                    <div className="spinner" style={{ width: '18px', height: '18px' }} />
                  ) : (
                    <span>Reject Plan</span>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Execute Recovery Modal */}
      {showExecuteModal && selectedPlan && (
        <div className="modal-overlay" onClick={() => setShowExecuteModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
            <div style={{
              padding: '1.25rem 1.5rem',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <h3 style={{ fontSize: '1.25rem' }}>Execute Recovery Plan</h3>
              <button onClick={() => setShowExecuteModal(false)} className="btn btn-secondary btn-sm" style={{ padding: '0.35rem' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '1.5rem' }}>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
                Executing this approved plan runs all {selectedPlan.actions?.length || 0} compensation actions sequentially.
              </p>

              <div style={{
                background: 'rgba(15, 23, 42, 0.7)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                marginBottom: '1.5rem',
              }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', cursor: 'pointer', fontWeight: 600 }}>
                  <input
                    type="checkbox"
                    checked={simulateExecFailure}
                    onChange={(e) => setSimulateExecFailure(e.target.checked)}
                    style={{ accentColor: 'var(--danger)', width: '18px', height: '18px' }}
                  />
                  <span>Simulate Action Failure</span>
                </label>

                {simulateExecFailure && (
                  <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">Fail at Action Order</label>
                      <select
                        value={failAtActionOrder}
                        onChange={(e) => setFailAtActionOrder(e.target.value)}
                        className="form-select"
                      >
                        {selectedPlan.actions?.map((a) => (
                          <option key={a.action_order} value={a.action_order}>
                            Action {a.action_order}: {a.action_type} (Step {a.target_step_order})
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">Simulated Failure Error</label>
                      <input
                        type="text"
                        value={execErrorMessage}
                        onChange={(e) => setExecErrorMessage(e.target.value)}
                        className="form-input"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button onClick={() => setShowExecuteModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button onClick={handleExecute} disabled={submittingAction} className="btn btn-primary">
                  {submittingAction ? (
                    <div className="spinner" style={{ width: '18px', height: '18px' }} />
                  ) : (
                    <span>Start Recovery Execution</span>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

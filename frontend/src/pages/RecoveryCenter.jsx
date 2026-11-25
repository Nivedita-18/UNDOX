import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ShieldCheck,
  Loader2,
  Search,
  FileText,
  Play,
  XCircle,
  ChevronDown,
  Activity,
} from "lucide-react";

import { getWorkflows } from "../api/workflows";
import { getWorkflowExecutions } from "../api/executions";

import {
  getRecoveryPlans,
  generateRecoveryPlan,
  checkRecoveryConflicts,
  approveRecoveryPlan,
  rejectRecoveryPlan,
  executeRecoveryPlan,
  getRecoveryExecutionStatus,
} from "../api/recovery";

import { useAuth } from "../context/AuthContext";
import { useDashboard } from "../context/DashboardContext";

import "./RecoveryCenter.css";


function getErrorMessage(error) {
  const detail = error.response?.data?.detail;

  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(", ");
  }

  return typeof detail === "string"
    ? detail
    : error.message || "Unable to complete the operation.";
}


function formatDate(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "Not available"
    : date.toLocaleString();
}


function RecoveryStatus({ status }) {
  const normalized = String(status || "UNKNOWN").toLowerCase();

  return (
    <span className={`recovery-status recovery-${normalized}`}>
      {status || "UNKNOWN"}
    </span>
  );
}


export default function RecoveryCenter() {
  const { user } = useAuth();
  const { refreshDashboard } = useDashboard();

  const role = String(user?.role || "").toUpperCase();

  const canManage = ["ADMIN", "OPERATOR"].includes(role);

  const [executions, setExecutions] = useState([]);
  const [plans, setPlans] = useState([]);

  const [selectedExecutionId, setSelectedExecutionId] = useState("");

  const [reports, setReports] = useState({});
  const [reviewInputs, setReviewInputs] = useState({});
  const [progressData, setProgressData] = useState({});

  const [search, setSearch] = useState("");

  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState(null);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");


  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const workflowResponse = await getWorkflows({
        limit: 100,
        offset: 0,
      });

      const workflows = Array.isArray(workflowResponse)
        ? workflowResponse
        : [];

      const executionResults = await Promise.all(
        workflows.map(async (workflow) => {
          try {
            const result = await getWorkflowExecutions(workflow.id, {
              limit: 100,
              offset: 0,
            });

            return (Array.isArray(result) ? result : []).map(
              (execution) => ({
                ...execution,
                workflow_name: workflow.name,
              })
            );
          } catch (requestError) {
            console.warn(
              `Unable to load workflow ${workflow.id} executions`,
              requestError
            );
            return [];
          }
        })
      );

      const allExecutions = executionResults.flat();

      setExecutions(allExecutions);

      const recoveryResults = await Promise.all(
        allExecutions.map(async (execution) => {
          try {
            const result = await getRecoveryPlans(execution.id);

            return (Array.isArray(result) ? result : []).map(
              (plan) => ({
                ...plan,
                workflow_name: execution.workflow_name,
                execution_status: execution.status,
              })
            );
          } catch (requestError) {
            console.warn(
              `Unable to load recovery plans for execution ${execution.id}`,
              requestError
            );

            return [];
          }
        })
      );

      const allPlans = recoveryResults
        .flat()
        .sort((first, second) => second.id - first.id);

      setPlans(allPlans);

      setSelectedExecutionId((current) => {
        const failed = allExecutions.filter(
          (item) => item.status === "FAILED"
        );

        if (
          current &&
          failed.some((item) => String(item.id) === String(current))
        ) {
          return current;
        }

        return failed.length ? String(failed[0].id) : "";
      });

    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, []);


  useEffect(() => {
    loadData();
  }, [loadData]);


  const failedExecutions = executions.filter(
    (execution) => execution.status === "FAILED"
  );


  const metrics = useMemo(() => ({
    total: plans.length,

    generated: plans.filter(
      (plan) => plan.status === "GENERATED"
    ).length,

    approved: plans.filter(
      (plan) => plan.status === "APPROVED"
    ).length,

    completed: plans.filter(
      (plan) => plan.status === "COMPLETED"
    ).length,

    failed: plans.filter(
      (plan) => plan.status === "FAILED"
    ).length,
  }), [plans]);


  const visiblePlans = plans.filter((plan) => {
    const value = search.toLowerCase();

    return (
      String(plan.id).includes(value) ||
      String(plan.execution_id).includes(value) ||
      String(plan.workflow_name || "").toLowerCase().includes(value) ||
      String(plan.status || "").toLowerCase().includes(value)
    );
  });


  function updateReview(planId, field, value) {
    setReviewInputs((previous) => ({
      ...previous,
      [planId]: {
        ...previous[planId],
        [field]: value,
      },
    }));
  }


  async function handleGenerate(event) {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!canManage) {
      setError("Only ADMIN and OPERATOR users can generate recovery plans.");
      return;
    }

    if (!selectedExecutionId) {
      setError("Select a failed execution first.");
      return;
    }

    try {
      setActingId("generate");

      const result = await generateRecoveryPlan(
        Number(selectedExecutionId)
      );

      setSuccess(
        `Recovery plan #${result.id} generated successfully.`
      );

      await loadData();
      refreshDashboard().catch(() => {});

    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setActingId(null);
    }
  }


  async function handleInspect(planId) {
    setError("");
    setSuccess("");

    try {
      setActingId(planId);

      const report = await checkRecoveryConflicts(planId);

      setReports((previous) => ({
        ...previous,
        [planId]: report,
      }));

      setSuccess(
        report.conflict_count > 0
          ? `${report.conflict_count} conflict(s) detected in plan #${planId}.`
          : `No conflicts detected in plan #${planId}.`
      );

      await loadData();

    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setActingId(null);
    }
  }


  async function handleDecision(plan, decision) {
    setError("");
    setSuccess("");

    if (!canManage) {
      setError("Only ADMIN and OPERATOR users can review recovery plans.");
      return;
    }

    const input = reviewInputs[plan.id] || {};
    const reason = String(input.reason || "").trim();

    if (reason.length < 3) {
      setError("Please enter a review reason containing at least 3 characters.");
      return;
    }

    const report = reports[plan.id];

    if (decision === "approve") {
      if (!report) {
        setError("Inspect recovery conflicts before approving the plan.");
        return;
      }

      if (report.conflict_count > 0) {
        setError("Resolve recovery conflicts before approval.");
        return;
      }

      const manualRequired =
        Array.isArray(report.manual_review_required) &&
        report.manual_review_required.length > 0;

      if (manualRequired && !input.manualAcknowledged) {
        setError("Acknowledge the manual review requirement before approval.");
        return;
      }
    }

    try {
      setActingId(plan.id);

      const payload = {
        reason,
        manual_review_acknowledged:
          Boolean(input.manualAcknowledged),
      };

      if (decision === "approve") {
        await approveRecoveryPlan(plan.id, payload);

        setSuccess(`Recovery plan #${plan.id} approved.`);
      } else {
        await rejectRecoveryPlan(plan.id, payload);

        setSuccess(`Recovery plan #${plan.id} rejected.`);
      }

      await loadData();
      refreshDashboard().catch(() => {});

    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setActingId(null);
    }
  }


  async function handleExecute(plan) {
    setError("");
    setSuccess("");

    if (!canManage) {
      setError("Only ADMIN and OPERATOR users can execute recovery plans.");
      return;
    }

    if (plan.status !== "APPROVED") {
      setError("Only approved recovery plans can be executed.");
      return;
    }

    const confirmed = window.confirm(
      `Execute approved recovery plan #${plan.id}?`
    );

    if (!confirmed) return;

    try {
      setActingId(plan.id);

      await executeRecoveryPlan(plan.id);

      setSuccess(`Recovery plan #${plan.id} execution completed.`);

      await loadData();
      refreshDashboard().catch(() => {});

    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setActingId(null);
    }
  }


  async function handleProgress(planId) {
    setError("");

    try {
      setActingId(planId);

      const result = await getRecoveryExecutionStatus(planId);

      setProgressData((previous) => ({
        ...previous,
        [planId]: result,
      }));

    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setActingId(null);
    }
  }


  return (
    <div className="page-container recovery-page">

      <div className="content-heading">
        <div>
          <span className="section-eyebrow">
            WORKSPACE / FAILURE MANAGEMENT
          </span>

          <h2>Recovery Plans</h2>

          <p>
            Generate recovery proposals, inspect conflicts and manage
            recovery approvals.
          </p>
        </div>

        <div className="heading-actions">
          <button
            className="filter-button"
            onClick={loadData}
            disabled={loading || actingId !== null}
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </div>


      {/* Recovery metrics */}

      <div className="metrics-grid">

        <article className="metric-card">
          <div className="metric-card-top">
            <span className="metric-icon purple">
              <FileText size={20} />
            </span>
          </div>

          <div className="metric-data">
            <span>Total Plans</span>
            <h3>{loading ? "..." : metrics.total}</h3>
            <p>Recorded recovery proposals</p>
          </div>
        </article>


        <article className="metric-card">
          <div className="metric-card-top">
            <span className="metric-icon blue">
              <Clock3 size={20} />
            </span>
          </div>

          <div className="metric-data">
            <span>Generated</span>
            <h3>{loading ? "..." : metrics.generated}</h3>
            <p>Awaiting review</p>
          </div>
        </article>


        <article className="metric-card">
          <div className="metric-card-top">
            <span className="metric-icon green">
              <ShieldCheck size={20} />
            </span>
          </div>

          <div className="metric-data">
            <span>Approved</span>
            <h3>{loading ? "..." : metrics.approved}</h3>
            <p>Ready for execution</p>
          </div>
        </article>


        <article className="metric-card">
          <div className="metric-card-top">
            <span className="metric-icon red">
              <AlertTriangle size={20} />
            </span>
          </div>

          <div className="metric-data">
            <span>Failed Plans</span>
            <h3>{loading ? "..." : metrics.failed}</h3>
            <p>Recovery execution failures</p>
          </div>
        </article>

      </div>


      {/* Generate recovery plan */}

      <section className="dashboard-panel recovery-generate-panel">

        <div className="panel-heading">
          <div>
            <h3>Generate Recovery Plan</h3>
            <p>
              Select a failed workflow execution to generate its recovery proposal.
            </p>
          </div>

          <div className="recovery-header-icon">
            <RefreshCw size={20} />
          </div>
        </div>


        {!canManage && (
          <div className="recovery-permission-note">
            <ShieldCheck size={19} />

            <div>
              <strong>Read-only access</strong>

              <p>
                Your role is {role || "VIEWER"}. ADMIN and OPERATOR
                accounts are required to generate or manage recovery plans.
              </p>
            </div>
          </div>
        )}


        <form
          className="recovery-generate-form"
          onSubmit={handleGenerate}
        >

          <label className="form-label">
            Select Failed Execution

            <select
              className="form-input"
              value={selectedExecutionId}
              onChange={(event) =>
                setSelectedExecutionId(event.target.value)
              }
              disabled={!canManage || loading || actingId === "generate"}
            >
              <option value="">Select a failed execution</option>

              {failedExecutions.map((execution) => (
                <option
                  key={execution.id}
                  value={execution.id}
                >
                  Execution #{execution.id} — {execution.workflow_name}
                </option>
              ))}
            </select>
          </label>


          <button
            className="primary-button"
            type="submit"
            disabled={
              !canManage ||
              loading ||
              actingId !== null ||
              !selectedExecutionId
            }
          >
            {actingId === "generate" ? (
              <>
                <Loader2 size={17} className="recovery-spinner" />
                Generating...
              </>
            ) : (
              <>
                <RefreshCw size={17} />
                Generate Recovery Plan
              </>
            )}
          </button>

        </form>


        {!loading && failedExecutions.length === 0 && (
          <div className="recovery-hint">
            <CheckCircle2 size={17} />
            No failed executions are currently available for recovery.
          </div>
        )}

      </section>


      {/* Feedback */}

      {error && (
        <div className="recovery-message recovery-error">
          <AlertTriangle size={19} />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="recovery-message recovery-success">
          <CheckCircle2 size={19} />
          <span>{success}</span>
        </div>
      )}


      {/* Recovery plan registry */}

      <section className="dashboard-panel recovery-registry">

        <div className="panel-heading">
          <div>
            <h3>Recovery Registry</h3>
            <p>
              {plans.length} recovery plans available
            </p>
          </div>
        </div>


        <div className="recovery-search">
          <Search size={17} />

          <input
            type="search"
            placeholder="Search by plan, execution or workflow..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>


        {loading ? (
          <div className="recovery-empty">
            <Loader2 size={25} className="recovery-spinner" />
            <p>Loading recovery plans...</p>
          </div>
        ) : visiblePlans.length === 0 ? (
          <div className="recovery-empty">
            <RefreshCw size={30} />

            <h3>No recovery plans found</h3>

            <p>
              Generate a plan from a failed execution to begin recovery.
            </p>
          </div>
        ) : (
          <div className="recovery-plan-list">

            {visiblePlans.map((plan) => {
              const report = reports[plan.id];
              const review = reviewInputs[plan.id] || {};
              const progress = progressData[plan.id];

              const manualRequired =
                Array.isArray(report?.manual_review_required) &&
                report.manual_review_required.length > 0;

              const busy = actingId === plan.id;

              return (
                <article
                  className="recovery-plan-card"
                  key={plan.id}
                >

                  <div className="recovery-plan-heading">

                    <div className="recovery-plan-title">
                      <div className="recovery-plan-icon">
                        <RefreshCw size={20} />
                      </div>

                      <div>
                        <strong>
                          Recovery Plan #{plan.id}
                        </strong>

                        <span>
                          {plan.workflow_name || "Workflow"} ·
                          {" "}Execution #{plan.execution_id}
                        </span>
                      </div>
                    </div>

                    <RecoveryStatus status={plan.status} />

                  </div>


                  <p className="recovery-plan-description">
                    {plan.description || "No recovery plan description available."}
                  </p>


                  <div className="recovery-plan-meta">
                    <div>
                      <span>Actions</span>
                      <strong>{plan.actions?.length ?? 0}</strong>
                    </div>

                    <div>
                      <span>Conflicts</span>
                      <strong>{plan.conflict_count ?? 0}</strong>
                    </div>

                    <div>
                      <span>Created</span>
                      <strong>{formatDate(plan.created_at)}</strong>
                    </div>

                    <div>
                      <span>Original execution</span>
                      <strong>{plan.execution_status || "Unknown"}</strong>
                    </div>
                  </div>


                  {/* Recovery action details */}

                  <details className="recovery-actions-details">

                    <summary>
                      <span>View Recovery Actions ({plan.actions?.length ?? 0})</span>
                      <ChevronDown size={16} />
                    </summary>

                    <div className="recovery-actions-list">

                      {(plan.actions || []).map((action) => (
                        <div
                          className="recovery-action-row"
                          key={action.id}
                        >

                          <div className="recovery-action-order">
                            {action.action_order}
                          </div>

                          <div className="recovery-action-content">
                            <strong>
                              {String(action.action_type).replaceAll("_", " ")}
                            </strong>

                            <span>
                              {action.description || "No action description"}
                            </span>

                            {action.requires_manual_review && (
                              <small>
                                Manual review required
                              </small>
                            )}

                            {action.error_message && (
                              <small className="recovery-action-error">
                                {action.error_message}
                              </small>
                            )}
                          </div>

                          <RecoveryStatus status={action.status} />

                        </div>
                      ))}

                    </div>

                  </details>


                  {/* Conflict inspection */}

                  <div className="recovery-plan-controls">

                    <button
                      type="button"
                      className="filter-button"
                      disabled={busy || actingId !== null}
                      onClick={() => handleInspect(plan.id)}
                    >
                      {busy ? (
                        <Loader2 size={16} className="recovery-spinner" />
                      ) : (
                        <ShieldCheck size={16} />
                      )}

                      Inspect Conflicts
                    </button>


                    {plan.status === "APPROVED" && canManage && (
                      <button
                        type="button"
                        className="primary-button"
                        disabled={actingId !== null}
                        onClick={() => handleExecute(plan)}
                      >
                        <Play size={16} />
                        Execute Recovery
                      </button>
                    )}


                    {["EXECUTING", "COMPLETED", "FAILED"].includes(plan.status) && (
                      <button
                        type="button"
                        className="filter-button"
                        disabled={actingId !== null}
                        onClick={() => handleProgress(plan.id)}
                      >
                        <Activity size={16} />
                        View Progress
                      </button>
                    )}

                  </div>


                  {/* Conflict report */}

                  {report && (
                    <div className="recovery-report">

                      <div className="recovery-report-heading">
                        <ShieldCheck size={18} />

                        <strong>Conflict Inspection Report</strong>

                        <span
                          className={
                            report.conflict_count > 0
                              ? "report-danger"
                              : "report-safe"
                          }
                        >
                          {report.conflict_count > 0
                            ? "CONFLICTS FOUND"
                            : "NO CONFLICTS"}
                        </span>
                      </div>


                      {(report.conflicts || []).length > 0 && (
                        <div className="recovery-conflict-list">

                          {report.conflicts.map((conflict, index) => (
                            <div
                              className="recovery-conflict-item"
                              key={`${conflict.type}-${index}`}
                            >
                              <AlertTriangle size={15} />

                              <span>
                                <strong>{conflict.type}</strong>
                                {" — "}
                                {conflict.message}
                              </span>
                            </div>
                          ))}

                        </div>
                      )}


                      {manualRequired && (
                        <div className="recovery-manual-warning">
                          <AlertTriangle size={17} />

                          <div>
                            <strong>Manual review required</strong>

                            <p>
                              {report.manual_review_required.length} action(s)
                              require explicit operator acknowledgement.
                            </p>
                          </div>
                        </div>
                      )}

                    </div>
                  )}


                  {/* Approval and rejection */}

                  {["GENERATED", "PENDING"].includes(plan.status) && (
                    <div className="recovery-review-form">

                      <label className="form-label">
                        Review / Decision Reason

                        <textarea
                          className="form-input form-textarea"
                          minLength={3}
                          maxLength={2000}
                          placeholder="Explain the reason for approving or rejecting this plan..."
                          value={review.reason || ""}
                          onChange={(event) =>
                            updateReview(plan.id, "reason", event.target.value)
                          }
                          disabled={!canManage || actingId !== null}
                        />
                      </label>


                      {manualRequired && (
                        <label className="recovery-acknowledgement">
                          <input
                            type="checkbox"
                            checked={Boolean(review.manualAcknowledged)}
                            onChange={(event) =>
                              updateReview(
                                plan.id,
                                "manualAcknowledged",
                                event.target.checked
                              )
                            }
                            disabled={!canManage || actingId !== null}
                          />

                          <span>
                            I acknowledge that manual review is required
                            for the listed recovery actions.
                          </span>
                        </label>
                      )}


                      {canManage && (
                        <div className="recovery-decision-buttons">

                          <button
                            type="button"
                            className="secondary-button recovery-reject-button"
                            disabled={actingId !== null}
                            onClick={() => handleDecision(plan, "reject")}
                          >
                            <XCircle size={16} />
                            Reject Plan
                          </button>


                          <button
                            type="button"
                            className="primary-button"
                            disabled={
                              actingId !== null ||
                              !report ||
                              report.conflict_count > 0 ||
                              (manualRequired && !review.manualAcknowledged)
                            }
                            title={
                              !report
                                ? "Inspect conflicts first"
                                : report.conflict_count > 0
                                  ? "Resolve conflicts before approval"
                                  : "Approve recovery plan"
                            }
                            onClick={() => handleDecision(plan, "approve")}
                          >
                            <CheckCircle2 size={16} />
                            Approve Plan
                          </button>

                        </div>
                      )}

                    </div>
                  )}


                  {progress && (
                    <div className="recovery-progress-panel">

                      <strong>Recovery Execution Progress</strong>

                      <div className="recovery-progress-grid">
                        <div>
                          <span>Total</span>
                          <strong>{progress.total_actions}</strong>
                        </div>

                        <div>
                          <span>Completed</span>
                          <strong>{progress.completed_actions}</strong>
                        </div>

                        <div>
                          <span>Failed</span>
                          <strong>{progress.failed_actions}</strong>
                        </div>

                        <div>
                          <span>Pending</span>
                          <strong>{progress.pending_actions}</strong>
                        </div>
                      </div>

                      <p>
                        Recovery status: {progress.status}
                      </p>

                    </div>
                  )}

                </article>
              );
            })}

          </div>
        )}

      </section>

    </div>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Play,
  RefreshCw,
  Workflow,
  ChevronDown,
  ChevronRight,
  Loader2,
  ShieldCheck,
} from "lucide-react";

import { getWorkflows } from "../api/workflows";

import {
  getWorkflowExecutions,
  executeWorkflow,
} from "../api/executions";

import { useAuth } from "../context/AuthContext";
import { useDashboard } from "../context/DashboardContext";

import "./ExecutionCenter.css";


function getErrorMessage(error) {
  const detail = error.response?.data?.detail;

  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(", ");
  }

  return typeof detail === "string"
    ? detail
    : error.message || "Unable to complete the request.";
}


function formatDate(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "Not available"
    : date.toLocaleString();
}


function StatusBadge({ status }) {
  const normalized = String(status || "UNKNOWN").toLowerCase();

  return (
    <span className={`execution-status status-${normalized}`}>
      {status || "UNKNOWN"}
    </span>
  );
}


export default function ExecutionCenter() {
  const { user } = useAuth();
  const { refreshDashboard } = useDashboard();

  const role = String(user?.role || "").toUpperCase();

  const canExecute = ["ADMIN", "OPERATOR"].includes(role);

  const [workflows, setWorkflows] = useState([]);
  const [executions, setExecutions] = useState([]);

  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");

  const [simulateFailure, setSimulateFailure] = useState(false);
  const [failureStepOrder, setFailureStepOrder] = useState("");
  const [failureMessage, setFailureMessage] = useState(
    "Simulated workflow step failure"
  );

  const [statusFilter, setStatusFilter] = useState("ALL");

  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");


  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const workflowResult = await getWorkflows({
        limit: 100,
        offset: 0,
      });

      const workflowList = Array.isArray(workflowResult)
        ? workflowResult
        : [];

      setWorkflows(workflowList);

      setSelectedWorkflowId((current) => {
        if (
          current &&
          workflowList.some(
            (workflow) => String(workflow.id) === String(current)
          )
        ) {
          return current;
        }

        return workflowList.length
          ? String(workflowList[0].id)
          : "";
      });

      const executionResults = await Promise.all(
        workflowList.map(async (workflow) => {
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
              `Could not load executions for workflow ${workflow.id}`,
              requestError
            );

            return [];
          }
        })
      );

      const allExecutions = executionResults
        .flat()
        .sort((first, second) => {
          const firstDate = new Date(
            first.created_at || first.started_at || 0
          ).getTime();

          const secondDate = new Date(
            second.created_at || second.started_at || 0
          ).getTime();

          return secondDate - firstDate;
        });

      setExecutions(allExecutions);

    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, []);


  useEffect(() => {
    loadData();
  }, [loadData]);


  const selectedWorkflow = workflows.find(
    (workflow) =>
      String(workflow.id) === String(selectedWorkflowId)
  );


  useEffect(() => {
    if (!selectedWorkflow?.steps?.length) {
      setFailureStepOrder("");
      return;
    }

    setFailureStepOrder((current) => {
      const valid = selectedWorkflow.steps.some(
        (step) => String(step.step_order) === String(current)
      );

      return valid
        ? current
        : String(selectedWorkflow.steps[0].step_order);
    });
  }, [selectedWorkflow]);


  const metrics = useMemo(() => {
    const status = (item) =>
      String(item.status || "").toUpperCase();

    return {
      total: executions.length,

      completed: executions.filter(
        (item) => status(item) === "COMPLETED"
      ).length,

      failed: executions.filter(
        (item) => status(item) === "FAILED"
      ).length,

      running: executions.filter(
        (item) =>
          ["RUNNING", "PENDING"].includes(status(item))
      ).length,
    };
  }, [executions]);


  const visibleExecutions = executions.filter((execution) => {
    return (
      statusFilter === "ALL" ||
      String(execution.status).toUpperCase() === statusFilter
    );
  });


  async function handleExecute(event) {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!canExecute) {
      setError("Only ADMIN and OPERATOR users can execute workflows.");
      return;
    }

    if (!selectedWorkflow) {
      setError("Please select a workflow.");
      return;
    }

    if (
      simulateFailure &&
      !selectedWorkflow.steps?.some(
        (step) => String(step.step_order) === String(failureStepOrder)
      )
    ) {
      setError("Please select a valid workflow step for failure simulation.");
      return;
    }

    try {
      setExecuting(true);

      const result = await executeWorkflow(
        selectedWorkflow.id,
        {
          simulate_failure: simulateFailure,
          failure_step_order: simulateFailure
            ? Number(failureStepOrder)
            : null,
          failure_message: failureMessage.trim() ||
            "Simulated workflow step failure",
        }
      );

      const resultStatus = String(result.status || "").toUpperCase();

      if (resultStatus === "FAILED") {
        setSuccess(
          `Execution #${result.id} recorded with a simulated failure.`
        );
      } else {
        setSuccess(
          `Workflow execution #${result.id} completed successfully.`
        );
      }

      setSimulateFailure(false);
      await loadData();

      refreshDashboard().catch(() => {});

    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setExecuting(false);
    }
  }


  return (
    <div className="page-container execution-page">

      <div className="content-heading">
        <div>
          <span className="section-eyebrow">
            WORKSPACE / MONITORING
          </span>

          <h2>Executions</h2>

          <p>
            Execute workflows, simulate failures and inspect
            step-level execution outcomes.
          </p>
        </div>

        <div className="heading-actions">
          <button
            className="filter-button"
            onClick={loadData}
            disabled={loading || executing}
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </div>


      {/* Execution metrics */}

      <div className="metrics-grid">

        <article className="metric-card">
          <div className="metric-card-top">
            <span className="metric-icon purple">
              <Activity size={20} />
            </span>
            <span className="execution-metric-label">ALL RECORDS</span>
          </div>

          <div className="metric-data">
            <span>Total Executions</span>
            <h3>{loading ? "..." : metrics.total}</h3>
            <p>Recorded workflow attempts</p>
          </div>
        </article>


        <article className="metric-card">
          <div className="metric-card-top">
            <span className="metric-icon green">
              <CheckCircle2 size={20} />
            </span>
          </div>

          <div className="metric-data">
            <span>Completed</span>
            <h3>{loading ? "..." : metrics.completed}</h3>
            <p>Successful executions</p>
          </div>
        </article>


        <article className="metric-card">
          <div className="metric-card-top">
            <span className="metric-icon red">
              <AlertTriangle size={20} />
            </span>
          </div>

          <div className="metric-data">
            <span>Failed</span>
            <h3>{loading ? "..." : metrics.failed}</h3>
            <p>Executions with failures</p>
          </div>
        </article>


        <article className="metric-card">
          <div className="metric-card-top">
            <span className="metric-icon blue">
              <Clock3 size={20} />
            </span>
          </div>

          <div className="metric-data">
            <span>Running / Pending</span>
            <h3>{loading ? "..." : metrics.running}</h3>
            <p>Active execution records</p>
          </div>
        </article>

      </div>


      {/* Execute workflow form */}

      <section className="dashboard-panel execute-panel">

        <div className="panel-heading">
          <div>
            <h3>Execute Workflow</h3>
            <p>
              Select a registered workflow to start a new execution.
            </p>
          </div>

          <div className="execution-panel-icon">
            <Play size={19} />
          </div>
        </div>


        {!canExecute && !loading && (
          <div className="execution-permission-note">
            <ShieldCheck size={20} />

            <div>
              <strong>Read-only access</strong>
              <p>
                Your account role is {role || "VIEWER"}.
                Only ADMIN and OPERATOR accounts can start executions.
              </p>
            </div>
          </div>
        )}


        {workflows.length === 0 && !loading ? (
          <div className="execution-empty">
            <Workflow size={29} />

            <h3>No workflows available</h3>

            <p>
              Create a workflow before starting an execution.
            </p>

            <Link to="/workflows/new" className="primary-button">
              <Workflow size={17} />
              Create Workflow
            </Link>
          </div>
        ) : (
          <form
            className="execution-form"
            onSubmit={handleExecute}
          >

            <label className="form-label">
              Select Workflow

              <select
                className="form-input"
                value={selectedWorkflowId}
                onChange={(event) =>
                  setSelectedWorkflowId(event.target.value)
                }
                disabled={loading || executing}
                required
              >
                {workflows.map((workflow) => (
                  <option
                    key={workflow.id}
                    value={workflow.id}
                  >
                    {workflow.name} (#{workflow.id})
                  </option>
                ))}
              </select>
            </label>


            {selectedWorkflow && (
              <div className="execution-workflow-info">
                <div>
                  <Workflow size={19} />

                  <div>
                    <strong>{selectedWorkflow.name}</strong>
                    <span>
                      {selectedWorkflow.steps?.length || 0} configured steps
                    </span>
                  </div>
                </div>

                <StatusBadge status={selectedWorkflow.status} />
              </div>
            )}


            <label className="execution-failure-toggle">
              <input
                type="checkbox"
                checked={simulateFailure}
                onChange={(event) =>
                  setSimulateFailure(event.target.checked)
                }
                disabled={!canExecute || executing}
              />

              <span>
                <strong>Enable Failure Simulation</strong>

                <small>
                  Intentionally fail a selected step to demonstrate recovery.
                </small>
              </span>
            </label>


            {simulateFailure && (
              <div className="execution-simulation-fields">

                <label className="form-label">
                  Failure Step

                  <select
                    className="form-input"
                    value={failureStepOrder}
                    onChange={(event) =>
                      setFailureStepOrder(event.target.value)
                    }
                    required
                    disabled={executing}
                  >
                    {(selectedWorkflow?.steps || []).map((step) => (
                      <option
                        key={step.id}
                        value={step.step_order}
                      >
                        Step {step.step_order}: {step.name}
                      </option>
                    ))}
                  </select>
                </label>


                <label className="form-label">
                  Failure Message

                  <input
                    className="form-input"
                    type="text"
                    maxLength={1000}
                    value={failureMessage}
                    onChange={(event) =>
                      setFailureMessage(event.target.value)
                    }
                    placeholder="Describe the simulated failure"
                  />
                </label>

                <div className="execution-simulation-warning">
                  <AlertTriangle size={17} />

                  <span>
                    Selected step will fail. All subsequent steps
                    will be marked as SKIPPED.
                  </span>
                </div>

              </div>
            )}


            <div className="execution-form-actions">

              <button
                type="submit"
                className="primary-button"
                disabled={
                  !canExecute ||
                  loading ||
                  executing ||
                  !selectedWorkflow ||
                  (simulateFailure && !failureStepOrder)
                }
              >
                {executing ? (
                  <>
                    <Loader2
                      size={18}
                      className="execution-spinner"
                    />
                    Executing...
                  </>
                ) : (
                  <>
                    <Play size={17} />
                    Start Execution
                  </>
                )}
              </button>

            </div>

          </form>
        )}

      </section>


      {/* Feedback */}

      {error && (
        <div className="execution-message execution-error">
          <AlertTriangle size={19} />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="execution-message execution-success">
          <CheckCircle2 size={19} />
          <span>{success}</span>
        </div>
      )}


      {/* Execution history */}

      <section className="dashboard-panel execution-history-panel">

        <div className="panel-heading">
          <div>
            <h3>Execution History</h3>
            <p>
              All available execution records across your workflows.
            </p>
          </div>

          <select
            className="execution-filter"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="ALL">All Statuses</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
            <option value="RUNNING">Running</option>
            <option value="PENDING">Pending</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>


        {loading ? (
          <div className="execution-empty">
            <Loader2 size={25} className="execution-spinner" />
            <p>Loading execution history...</p>
          </div>
        ) : visibleExecutions.length === 0 ? (
          <div className="execution-empty">
            <Activity size={30} />

            <h3>No executions found</h3>

            <p>
              Start a workflow execution to create your first record.
            </p>
          </div>
        ) : (
          <div className="execution-history-list">

            {visibleExecutions.map((execution) => (
              <details
                className="execution-record"
                key={execution.id}
              >

                <summary className="execution-record-summary">

                  <div className="execution-record-main">
                    <div className="execution-record-icon">
                      <Workflow size={19} />
                    </div>

                    <div>
                      <strong>
                        {execution.workflow_name}
                      </strong>

                      <span>
                        Execution #{execution.id} · Workflow #{execution.workflow_id}
                      </span>
                    </div>
                  </div>


                  <div className="execution-record-meta">
                    <StatusBadge status={execution.status} />

                    <span>
                      {formatDate(execution.created_at)}
                    </span>

                    <ChevronDown size={17} />
                  </div>

                </summary>


                <div className="execution-record-details">

                  {execution.error_message && (
                    <div className="execution-error-detail">
                      <AlertTriangle size={17} />
                      <span>{execution.error_message}</span>
                    </div>
                  )}

                  <div className="execution-detail-grid">
                    <div>
                      <span>Started At</span>
                      <strong>
                        {formatDate(execution.started_at)}
                      </strong>
                    </div>

                    <div>
                      <span>Finished At</span>
                      <strong>
                        {formatDate(execution.finished_at)}
                      </strong>
                    </div>

                    <div>
                      <span>Triggered By</span>
                      <strong>
                        {execution.triggered_by ?? "System / Unknown"}
                      </strong>
                    </div>

                    <div>
                      <span>Execution Steps</span>
                      <strong>
                        {execution.steps?.length ?? 0}
                      </strong>
                    </div>
                  </div>


                  <h4>Step Execution Details</h4>

                  {(execution.steps || []).length === 0 ? (
                    <p>No step details available.</p>
                  ) : (
                    <div className="execution-step-list">

                      {execution.steps.map((step) => (
                        <div
                          className="execution-step-row"
                          key={step.id}
                        >
                          <div className="execution-step-order">
                            {step.step_order}
                          </div>

                          <div className="execution-step-content">
                            <strong>{step.step_name}</strong>

                            {step.error_message && (
                              <p>{step.error_message}</p>
                            )}
                          </div>

                          <StatusBadge status={step.status} />

                        </div>
                      ))}

                    </div>
                  )}

                </div>

              </details>
            ))}

          </div>
        )}

      </section>

    </div>
  );
}

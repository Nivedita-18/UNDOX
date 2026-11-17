import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  Plus,
  Search,
  Workflow,
  ArrowLeft,
  Trash2,
  Save,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  RefreshCw,
} from "lucide-react";

import {
  getWorkflows,
  createWorkflow,
} from "../api/workflows";

import { useDashboard } from "../context/DashboardContext";
import { useAuth } from "../context/AuthContext";

import "./WorkflowCenter.css";

function getErrorMessage(error) {
  const detail = error.response?.data?.detail;

  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(", ");
  }

  return typeof detail === "string"
    ? detail
    : error.message || "Something went wrong.";
}

function formatDate(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "Not available"
    : date.toLocaleDateString();
}

function createEmptyStep() {
  return {
    name: "",
    payloadText: "{}",
    compensationText: "{}",
    is_reversible: false,
  };
}

function parseJsonObject(value, fieldName) {
  let parsed;

  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error(`${fieldName} must contain valid JSON.`);
  }

  if (
    parsed === null ||
    typeof parsed !== "object" ||
    Array.isArray(parsed)
  ) {
    throw new Error(`${fieldName} must be a JSON object.`);
  }

  return parsed;
}


// Workflow listing
function WorkflowList() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const canCreate = ["ADMIN", "OPERATOR"].includes(
    String(user?.role || "").toUpperCase()
  );

  const [workflows, setWorkflows] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadWorkflows() {
    try {
      setLoading(true);
      setError("");

      const result = await getWorkflows({
        limit: 100,
        offset: 0,
      });

      setWorkflows(Array.isArray(result) ? result : []);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadWorkflows();
  }, []);

  const filteredWorkflows = workflows.filter((workflow) =>
    `${workflow.name} ${workflow.description || ""}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  return (
    <div className="page-container workflow-page">

      <div className="content-heading">
        <div>
          <span className="section-eyebrow">
            WORKSPACE / AUTOMATION
          </span>

          <h2>Workflows</h2>

          <p>
            Create, organize and manage sequential business workflows.
          </p>
        </div>

        <div className="heading-actions">
          {canCreate && (
            <button
              className="primary-button"
              onClick={() => navigate("/workflows/new")}
            >
              <Plus size={18} />
              Create Workflow
            </button>
          )}
        </div>
      </div>

      <div className="workflow-toolbar">
        <div className="search-field table-search">
          <Search size={17} />

          <input
            type="search"
            placeholder="Search workflows..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>

        <button
          className="filter-button"
          onClick={loadWorkflows}
          disabled={loading}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="workflow-message workflow-error">
          <AlertTriangle size={19} />
          <span>{error}</span>
        </div>
      )}

      <section className="dashboard-panel table-panel">
        <div className="panel-heading">
          <div>
            <h3>Workflow Registry</h3>
            <p>
              {workflows.length} workflow records loaded
            </p>
          </div>
        </div>

        <div className="workflow-table">

          <div className="workflow-table-header">
            <span>WORKFLOW</span>
            <span>STEPS</span>
            <span>STATUS</span>
            <span>CREATED</span>
            <span>DETAIL</span>
          </div>

          {loading ? (
            <div className="workflow-state">
              <Loader2 className="workflow-spinner" size={27} />
              <p>Loading workflows...</p>
            </div>
          ) : filteredWorkflows.length === 0 ? (
            <div className="workflow-state">
              <Workflow size={32} />
              <h3>
                {search
                  ? "No matching workflows"
                  : "No workflows created yet"}
              </h3>
              <p>
                {search
                  ? "Try another search term."
                  : "Create your first workflow to get started."}
              </p>

              {!search && canCreate && (
                <button
                  className="primary-button"
                  onClick={() => navigate("/workflows/new")}
                >
                  <Plus size={17} />
                  Create First Workflow
                </button>
              )}
            </div>
          ) : (
            filteredWorkflows.map((workflow) => (
              <div className="workflow-table-row" key={workflow.id}>
                <div className="workflow-name-cell">
                  <div className="workflow-row-icon">
                    <Workflow size={19} />
                  </div>

                  <div>
                    <strong>{workflow.name}</strong>
                    <span>
                      {workflow.description || "No description"}
                    </span>
                  </div>
                </div>

                <span className="workflow-step-count">
                  {workflow.steps?.length ?? 0} steps
                </span>

                <span
                  className={`workflow-status ${
                    String(workflow.status).toLowerCase()
                  }`}
                >
                  {workflow.status}
                </span>

                <span className="workflow-date">
                  {formatDate(workflow.created_at)}
                </span>

                <span className="workflow-id">
                  #{workflow.id}
                </span>
              </div>
            ))
          )}

        </div>
      </section>

    </div>
  );
}


// Workflow creation and step builder
function WorkflowBuilder() {
  const navigate = useNavigate();
  const { refreshDashboard } = useDashboard();
  const { user } = useAuth();

  const canCreate = ["ADMIN", "OPERATOR"].includes(
    String(user?.role || "").toUpperCase()
  );

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const [steps, setSteps] = useState([
    createEmptyStep(),
  ]);

  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function updateStep(index, field, value) {
    setSteps((previous) =>
      previous.map((step, stepIndex) =>
        stepIndex === index
          ? { ...step, [field]: value }
          : step
      )
    );
  }

  function addStep() {
    setSteps((previous) => [
      ...previous,
      createEmptyStep(),
    ]);
  }

  function removeStep(index) {
    setSteps((previous) =>
      previous.filter((_, stepIndex) => stepIndex !== index)
    );
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (!canCreate) {
      setError("Only ADMIN and OPERATOR users can create workflows.");
      return;
    }

    if (!name.trim()) {
      setError("Workflow name is required.");
      return;
    }

    if (steps.length === 0) {
      setError("A workflow must contain at least one step.");
      return;
    }

    try {
      const formattedSteps = steps.map((step, index) => {
        if (!step.name.trim()) {
          throw new Error(`Please enter a name for Step ${index + 1}.`);
        }

        const payload = parseJsonObject(
          step.payloadText,
          `Step ${index + 1} input payload`
        );

        const compensationPayload = step.is_reversible
          ? parseJsonObject(
              step.compensationText,
              `Step ${index + 1} compensation payload`
            )
          : null;

        return {
          name: step.name.trim(),
          step_order: index + 1,
          payload,
          compensation_payload: compensationPayload,
          is_reversible: step.is_reversible,
        };
      });

      setSaving(true);

      await createWorkflow({
        name: name.trim(),
        description: description.trim() || null,
        steps: formattedSteps,
      });

      try {
        await refreshDashboard();
      } catch {
        // Workflow creation has already succeeded.
      }

      navigate("/workflows", { replace: true });

    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-container workflow-page">

      <div className="content-heading">
        <div>
          <span className="section-eyebrow">
            WORKSPACE / AUTOMATION / NEW
          </span>

          <h2>Create Workflow</h2>

          <p>
            Configure your workflow and define its ordered execution steps.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>

        {!canCreate && (
          <div className="workflow-message workflow-error">
            Only ADMIN and OPERATOR users can create workflows.
          </div>
        )}

        {error && (
          <div className="workflow-message workflow-error">
            <AlertTriangle size={19} />
            <span>{error}</span>
          </div>
        )}

        <section className="dashboard-panel workflow-builder-panel">

          <div className="panel-heading">
            <div>
              <h3>Workflow Information</h3>
              <p>Basic details of your workflow definition</p>
            </div>
          </div>

          <div className="form-content">

            <label className="form-label">
              Workflow Name
              <input
                className="form-input"
                type="text"
                maxLength={150}
                placeholder="e.g. Order Fulfillment Workflow"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
              />
            </label>

            <label className="form-label">
              Description
              <textarea
                className="form-input form-textarea"
                placeholder="Describe what this workflow will do..."
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>

          </div>
        </section>

        <section className="workflow-steps-section">

          <div className="workflow-steps-heading">
            <div>
              <span className="section-eyebrow">
                EXECUTION DESIGN
              </span>

              <h3>Workflow Steps</h3>

              <p>
                Steps will execute in the order shown below.
              </p>
            </div>

            <span className="workflow-step-badge">
              {steps.length} {steps.length === 1 ? "STEP" : "STEPS"}
            </span>
          </div>

          {steps.map((step, index) => (
            <article
              className="dashboard-panel workflow-step-card"
              key={index}
            >

              <div className="workflow-step-card-heading">
                <div className="workflow-step-number">
                  {index + 1}
                </div>

                <div>
                  <strong>Step {index + 1}</strong>
                  <span>Execution configuration</span>
                </div>

                {steps.length > 1 && (
                  <button
                    type="button"
                    className="workflow-remove-button"
                    onClick={() => removeStep(index)}
                    aria-label={`Remove step ${index + 1}`}
                  >
                    <Trash2 size={17} />
                    Remove
                  </button>
                )}
              </div>

              <div className="form-content workflow-step-fields">

                <label className="form-label">
                  Step Name
                  <input
                    className="form-input"
                    type="text"
                    maxLength={150}
                    placeholder="e.g. Validate Customer Order"
                    value={step.name}
                    onChange={(event) =>
                      updateStep(index, "name", event.target.value)
                    }
                    required
                  />
                </label>

                <label className="form-label">
                  Input Payload (JSON)
                  <textarea
                    className="form-input workflow-json-input"
                    spellCheck="false"
                    value={step.payloadText}
                    onChange={(event) =>
                      updateStep(index, "payloadText", event.target.value)
                    }
                  />
                  <span className="workflow-field-hint">
                    Enter an object containing this step's input data.
                  </span>
                </label>

                <label className="workflow-reversible-option">
                  <input
                    type="checkbox"
                    checked={step.is_reversible}
                    onChange={(event) =>
                      updateStep(
                        index,
                        "is_reversible",
                        event.target.checked
                      )
                    }
                  />

                  <span>
                    <strong>Reversible Step</strong>
                    <small>
                      This step has a compensation operation.
                    </small>
                  </span>
                </label>

                {step.is_reversible && (
                  <label className="form-label">
                    Compensation Payload (JSON)
                    <textarea
                      className="form-input workflow-json-input"
                      spellCheck="false"
                      value={step.compensationText}
                      onChange={(event) =>
                        updateStep(
                          index,
                          "compensationText",
                          event.target.value
                        )
                      }
                    />

                    <span className="workflow-field-hint">
                      Define the action used to reverse this step.
                    </span>
                  </label>
                )}

              </div>

            </article>
          ))}

          <button
            type="button"
            className="workflow-add-step-button"
            onClick={addStep}
          >
            <Plus size={18} />
            Add Another Step
          </button>

        </section>

        <div className="workflow-submit-bar">

          <button
            type="button"
            className="secondary-button"
            onClick={() => navigate("/workflows")}
            disabled={saving}
          >
            <ArrowLeft size={16} />
            Cancel
          </button>

          <button
            type="submit"
            className="primary-button"
            disabled={saving || !canCreate}
          >
            {saving ? (
              <>
                <Loader2 size={17} className="workflow-spinner" />
                Saving Workflow...
              </>
            ) : (
              <>
                <Save size={17} />
                Save Workflow
                <ChevronRight size={17} />
              </>
            )}
          </button>

        </div>

      </form>

    </div>
  );
}


export default function WorkflowCenter({ mode = "list" }) {
  if (mode === "create") {
    return <WorkflowBuilder />;
  }

  return <WorkflowList />;
}

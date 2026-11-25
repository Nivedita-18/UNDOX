import { useCallback, useEffect, useState } from "react";

import {
  FileText,
  Search,
  RefreshCw,
  ShieldCheck,
  AlertTriangle,
  Loader2,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Activity,
  CalendarDays,
} from "lucide-react";

import {
  getAuditLogs,
} from "../api/audit";

import { useAuth } from "../context/AuthContext";

import "./AuditCenter.css";


const PAGE_SIZE = 20;


function formatDate(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "Not available"
    : date.toLocaleString();
}


function formatEventName(value) {
  return String(value || "SYSTEM_EVENT")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}


function getErrorMessage(error) {
  const detail = error.response?.data?.detail;

  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(", ");
  }

  return typeof detail === "string"
    ? detail
    : error.message || "Unable to load audit records.";
}


function OutcomeBadge({ outcome }) {
  const normalized = String(outcome || "UNKNOWN").toLowerCase();

  return (
    <span className={`audit-outcome audit-outcome-${normalized}`}>
      {outcome || "UNKNOWN"}
    </span>
  );
}


export default function AuditCenter() {
  const { user } = useAuth();

  const role = String(user?.role || "").toUpperCase();

  const canViewAudit = ["ADMIN", "OPERATOR"].includes(role);

  const [events, setEvents] = useState([]);

  const [filters, setFilters] = useState({
    event_type: "",
    outcome: "",
    execution_id: "",
    recovery_plan_id: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [accessDenied, setAccessDenied] = useState(false);

  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);


  const loadEvents = useCallback(async (requestedOffset = 0) => {
    if (!canViewAudit) return;

    setLoading(true);
    setError("");
    setAccessDenied(false);

    const params = {
      limit: PAGE_SIZE,
      offset: requestedOffset,
    };

    if (filters.event_type.trim()) {
      params.event_type = filters.event_type.trim();
    }

    if (filters.outcome) {
      params.outcome = filters.outcome;
    }

    if (filters.execution_id.trim()) {
      params.execution_id = Number(filters.execution_id);
    }

    if (filters.recovery_plan_id.trim()) {
      params.recovery_plan_id = Number(filters.recovery_plan_id);
    }

    try {
      const result = await getAuditLogs(params);

      const records = Array.isArray(result) ? result : [];

      setEvents(records);
      setOffset(requestedOffset);
      setHasMore(records.length === PAGE_SIZE);

    } catch (requestError) {
      const status = requestError.response?.status;

      if (status === 403 || status === 401) {
        setAccessDenied(true);
      }

      setEvents([]);
      setHasMore(false);
      setError(getErrorMessage(requestError));

    } finally {
      setLoading(false);
    }
  }, [canViewAudit, filters]);


  useEffect(() => {
    if (canViewAudit) {
      loadEvents(0);
    }
  }, [canViewAudit, loadEvents]);


  function updateFilter(field, value) {
    setFilters((previous) => ({
      ...previous,
      [field]: value,
    }));
  }


  function handleSearch(event) {
    event.preventDefault();

    if (
      filters.execution_id &&
      (!Number.isInteger(Number(filters.execution_id)) ||
        Number(filters.execution_id) <= 0)
    ) {
      setError("Execution ID must be a positive integer.");
      return;
    }

    if (
      filters.recovery_plan_id &&
      (!Number.isInteger(Number(filters.recovery_plan_id)) ||
        Number(filters.recovery_plan_id) <= 0)
    ) {
      setError("Recovery Plan ID must be a positive integer.");
      return;
    }

    loadEvents(0);
  }


  function handleReset() {
    setFilters({
      event_type: "",
      outcome: "",
      execution_id: "",
      recovery_plan_id: "",
    });
  }


  // Role-based access restriction
  if (!canViewAudit) {
    return (
      <div className="page-container audit-page">

        <div className="content-heading">
          <div>
            <span className="section-eyebrow">
              WORKSPACE / SECURITY
            </span>

            <h2>Audit Logs</h2>

            <p>Inspect important workflow and recovery events.</p>
          </div>
        </div>

        <div className="dashboard-panel audit-access-denied">

          <ShieldCheck size={43} />

          <h3>Audit Access Restricted</h3>

          <p>
            Your current account role is {role || "VIEWER"}.
            Audit history is available only to ADMIN and OPERATOR users.
          </p>

        </div>
      </div>
    );
  }


  return (
    <div className="page-container audit-page">

      <div className="content-heading">
        <div>
          <span className="section-eyebrow">
            WORKSPACE / SECURITY
          </span>

          <h2>Audit Logs</h2>

          <p>
            Inspect important workflow, execution and recovery events.
          </p>
        </div>

        <div className="heading-actions">
          <button
            className="filter-button"
            onClick={() => loadEvents(offset)}
            disabled={loading}
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </div>


      {/* Audit information */}

      <div className="audit-info-banner">
        <ShieldCheck size={21} />

        <div>
          <strong>Secure Audit History</strong>

          <p>
            System activities are recorded with timestamps,
            event outcomes and associated execution references.
          </p>
        </div>
      </div>


      {/* Filters */}

      <section className="dashboard-panel audit-filter-panel">

        <div className="panel-heading">
          <div>
            <h3>Filter Events</h3>
            <p>Search audit history using backend-supported filters.</p>
          </div>
        </div>


        <form onSubmit={handleSearch} className="audit-filter-form">

          <label className="form-label">
            Event Type

            <input
              className="form-input"
              type="text"
              placeholder="e.g. RECOVERY_PLAN_APPROVED"
              value={filters.event_type}
              onChange={(event) =>
                updateFilter("event_type", event.target.value)
              }
            />
          </label>


          <label className="form-label">
            Outcome

            <select
              className="form-input"
              value={filters.outcome}
              onChange={(event) =>
                updateFilter("outcome", event.target.value)
              }
            >
              <option value="">All Outcomes</option>
              <option value="SUCCESS">SUCCESS</option>
              <option value="FAILED">FAILED</option>
              <option value="REJECTED">REJECTED</option>
            </select>
          </label>


          <label className="form-label">
            Execution ID

            <input
              className="form-input"
              type="number"
              min="1"
              placeholder="Execution ID"
              value={filters.execution_id}
              onChange={(event) =>
                updateFilter("execution_id", event.target.value)
              }
            />
          </label>


          <label className="form-label">
            Recovery Plan ID

            <input
              className="form-input"
              type="number"
              min="1"
              placeholder="Recovery Plan ID"
              value={filters.recovery_plan_id}
              onChange={(event) =>
                updateFilter("recovery_plan_id", event.target.value)
              }
            />
          </label>


          <div className="audit-filter-actions">

            <button
              type="button"
              className="secondary-button"
              onClick={handleReset}
              disabled={loading}
            >
              Reset Filters
            </button>

            <button
              type="submit"
              className="primary-button"
              disabled={loading}
            >
              <Search size={17} />
              Apply Filters
            </button>

          </div>

        </form>
      </section>


      {/* Error display */}

      {error && (
        <div className="audit-error-message">
          <AlertTriangle size={18} />

          <span>
            {accessDenied
              ? "Your account is not authorized to access audit records."
              : error}
          </span>
        </div>
      )}


      {/* Event records */}

      <section className="dashboard-panel audit-registry">

        <div className="panel-heading">

          <div>
            <h3>Event History</h3>

            <p>
              {loading
                ? "Retrieving audit records..."
                : `${events.length} events in this page`}
            </p>
          </div>

          <span className="audit-page-indicator">
            Page {Math.floor(offset / PAGE_SIZE) + 1}
          </span>

        </div>


        {loading ? (
          <div className="audit-empty">
            <Loader2 size={27} className="audit-spinner" />
            <p>Loading audit events...</p>
          </div>
        ) : events.length === 0 ? (
          <div className="audit-empty">
            <FileText size={34} />

            <h3>No audit events found</h3>

            <p>
              Try changing your filters or perform a workflow operation
              to generate audit history.
            </p>
          </div>
        ) : (
          <div className="audit-event-list">

            {events.map((event) => (
              <details
                className="audit-event-card"
                key={event.id}
              >

                <summary className="audit-event-summary">

                  <div className="audit-event-icon">
                    <Activity size={18} />
                  </div>

                  <div className="audit-event-main">

                    <strong>
                      {formatEventName(event.event_type)}
                    </strong>

                    <span>
                      Event #{event.id}
                      {" · "}
                      {formatDate(event.created_at)}
                    </span>

                  </div>

                  <OutcomeBadge outcome={event.outcome} />

                  <ChevronDown size={17} className="audit-chevron" />

                </summary>


                <div className="audit-event-details">

                  <p className="audit-event-message">
                    {event.message || "No event message available."}
                  </p>

                  <div className="audit-event-metadata">

                    <div>
                      <span>Actor ID</span>
                      <strong>{event.actor_id ?? "System"}</strong>
                    </div>

                    <div>
                      <span>Execution ID</span>
                      <strong>{event.execution_id ?? "—"}</strong>
                    </div>

                    <div>
                      <span>Recovery Plan ID</span>
                      <strong>{event.recovery_plan_id ?? "—"}</strong>
                    </div>

                    <div>
                      <span>Event Time</span>
                      <strong>{formatDate(event.created_at)}</strong>
                    </div>

                  </div>


                  {event.event_data && (
                    <div className="audit-json-section">

                      <strong>Event Data</strong>

                      <pre>
                        {JSON.stringify(event.event_data, null, 2)}
                      </pre>

                    </div>
                  )}

                </div>

              </details>
            ))}

          </div>
        )}


        {/* Pagination */}

        <div className="audit-pagination">

          <span>
            Showing {events.length} records
          </span>

          <div>

            <button
              className="secondary-button"
              disabled={loading || offset === 0}
              onClick={() =>
                loadEvents(Math.max(0, offset - PAGE_SIZE))
              }
            >
              <ChevronLeft size={16} />
              Previous
            </button>

            <button
              className="secondary-button"
              disabled={loading || !hasMore}
              onClick={() =>
                loadEvents(offset + PAGE_SIZE)
              }
            >
              Next
              <ChevronRight size={16} />
            </button>

          </div>

        </div>

      </section>


      <div className="audit-footer-note">
        <CalendarDays size={16} />

        <span>
          Audit timestamps are displayed using your browser's local timezone.
        </span>
      </div>

    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, 
  Filter, 
  RotateCcw, 
  ChevronLeft, 
  ChevronRight, 
  Search, 
  X, 
  Info,
  Calendar,
  User,
  Activity
} from 'lucide-react';
import { api } from '../api/client';

export default function AuditLogsView({ showToast }) {
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [selectedEventType, setSelectedEventType] = useState('');
  const [selectedOutcome, setSelectedOutcome] = useState('');
  const [searchExecutionId, setSearchExecutionId] = useState('');
  const [searchPlanId, setSearchPlanId] = useState('');

  // Pagination
  const [limit, setLimit] = useState(25);
  const [offset, setOffset] = useState(0);

  // Event modal inspector
  const [inspectEvent, setInspectEvent] = useState(null);

  const eventTypes = [
    'WORKFLOW_EXECUTION_STARTED',
    'WORKFLOW_EXECUTION_COMPLETED',
    'WORKFLOW_EXECUTION_FAILED',
    'RECOVERY_PLAN_CREATED',
    'RECOVERY_PLAN_APPROVED',
    'RECOVERY_PLAN_REJECTED',
    'RECOVERY_EXECUTION_STARTED',
    'RECOVERY_EXECUTION_COMPLETED',
    'RECOVERY_EXECUTION_FAILED',
  ];

  const outcomes = ['SUCCESS', 'FAILURE', 'BLOCKED', 'INFO'];

  const fetchAuditEvents = async () => {
    setLoading(true);
    try {
      const params = {
        limit,
        offset,
      };
      if (selectedEventType) params.event_type = selectedEventType;
      if (selectedOutcome) params.outcome = selectedOutcome;
      if (searchExecutionId.trim()) params.execution_id = searchExecutionId.trim();
      if (searchPlanId.trim()) params.recovery_plan_id = searchPlanId.trim();

      const res = await api.audit.listEvents(params);
      setEvents(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      showToast(`Failed to load audit history: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditEvents();
  }, [limit, offset, selectedEventType, selectedOutcome]);

  const handleApplyFilter = (e) => {
    e.preventDefault();
    setOffset(0);
    fetchAuditEvents();
  };

  const handleClearFilters = () => {
    setSelectedEventType('');
    setSelectedOutcome('');
    setSearchExecutionId('');
    setSearchPlanId('');
    setOffset(0);
  };

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit) || 1;

  const getOutcomeBadgeClass = (outcome) => {
    switch (outcome?.toUpperCase()) {
      case 'SUCCESS':
        return 'badge-completed';
      case 'FAILURE':
        return 'badge-failed';
      case 'BLOCKED':
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
          <h1 style={{ fontSize: '1.875rem', fontWeight: 800 }}>Audit History & Activity Ledger</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem', marginTop: '0.25rem' }}>
            Immutable, append-only security logs of all workflow transitions and operator recovery decisions.
          </p>
        </div>
        <button onClick={fetchAuditEvents} className="btn btn-secondary">
          <RotateCcw size={15} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
        <form onSubmit={handleApplyFilter} style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'flex-end' }}>
          {/* Event Type Filter */}
          <div style={{ flex: '1 1 200px' }}>
            <label className="form-label">Event Type</label>
            <select
              value={selectedEventType}
              onChange={(e) => {
                setSelectedEventType(e.target.value);
                setOffset(0);
              }}
              className="form-select"
            >
              <option value="">All Event Types</option>
              {eventTypes.map((et) => (
                <option key={et} value={et}>{et}</option>
              ))}
            </select>
          </div>

          {/* Outcome Filter */}
          <div style={{ flex: '1 1 140px' }}>
            <label className="form-label">Outcome</label>
            <select
              value={selectedOutcome}
              onChange={(e) => {
                setSelectedOutcome(e.target.value);
                setOffset(0);
              }}
              className="form-select"
            >
              <option value="">All Outcomes</option>
              {outcomes.map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
          </div>

          {/* Execution ID filter */}
          <div style={{ flex: '1 1 200px' }}>
            <label className="form-label">Execution UUID</label>
            <input
              type="text"
              placeholder="Filter by Execution ID..."
              value={searchExecutionId}
              onChange={(e) => setSearchExecutionId(e.target.value)}
              className="form-input"
            />
          </div>

          {/* Plan ID filter */}
          <div style={{ flex: '1 1 200px' }}>
            <label className="form-label">Plan UUID</label>
            <input
              type="text"
              placeholder="Filter by Plan ID..."
              value={searchPlanId}
              onChange={(e) => setSearchPlanId(e.target.value)}
              className="form-input"
            />
          </div>

          {/* Buttons */}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button type="submit" className="btn btn-primary">
              <Search size={15} />
              <span>Filter</span>
            </button>
            <button type="button" onClick={handleClearFilters} className="btn btn-secondary">
              <X size={15} />
              <span>Clear</span>
            </button>
          </div>
        </form>
      </div>

      {/* Audit Log Table */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Showing {events.length} of {total} recorded security events
          </div>

          {/* Limit selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem' }}>
            <span style={{ color: 'var(--text-muted)' }}>Per page:</span>
            <select
              value={limit}
              onChange={(e) => {
                setLimit(Number(e.target.value));
                setOffset(0);
              }}
              className="form-select"
              style={{ width: 'auto', padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="state-container" style={{ minHeight: '30vh' }}>
            <div className="spinner" />
          </div>
        ) : events.length === 0 ? (
          <div className="state-container" style={{ padding: '3rem 1rem' }}>
            <ShieldCheck size={40} color="#818cf8" />
            <h4 style={{ marginTop: '0.75rem', fontSize: '1.125rem' }}>No Audit Events Found</h4>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem', marginTop: '0.25rem' }}>
              Try loosening your search filters or executing workflows to generate trace records.
            </p>
          </div>
        ) : (
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Event Type</th>
                  <th>Outcome</th>
                  <th>Operator</th>
                  <th>Message Summary</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.id}>
                    <td style={{ whiteSpace: 'nowrap', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {new Date(ev.timestamp).toLocaleString()}
                    </td>
                    <td>
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.8125rem' }}>
                        {ev.event_type}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${getOutcomeBadgeClass(ev.outcome)}`} style={{ fontSize: '0.6875rem' }}>
                        {ev.outcome}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                      {ev.operator ? `@${ev.operator}` : 'system'}
                    </td>
                    <td style={{ maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.8125rem' }}>
                      {ev.message || '—'}
                    </td>
                    <td>
                      <button
                        onClick={() => setInspectEvent(ev)}
                        className="btn btn-secondary btn-sm"
                        style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginTop: '1.5rem',
          paddingTop: '1rem',
          borderTop: '1px solid var(--border-subtle)',
          flexWrap: 'wrap',
          gap: '1rem',
        }}>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            Page {currentPage} of {totalPages}
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="btn btn-secondary btn-sm"
            >
              <ChevronLeft size={16} />
              <span>Previous</span>
            </button>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              className="btn btn-secondary btn-sm"
            >
              <span>Next</span>
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Inspect Event Modal */}
      {inspectEvent && (
        <div className="modal-overlay" onClick={() => setInspectEvent(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <div style={{
              padding: '1.25rem 1.5rem',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <div>
                <h3 style={{ fontSize: '1.1875rem' }}>Audit Event Details</h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                  ID: {inspectEvent.id}
                </span>
              </div>
              <button onClick={() => setInspectEvent(null)} className="btn btn-secondary btn-sm" style={{ padding: '0.35rem' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '1.5rem', maxHeight: '70vh', overflowY: 'auto' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem', marginBottom: '1.25rem' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Event Type</div>
                  <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                    {inspectEvent.event_type}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Outcome Status</div>
                  <div style={{ marginTop: '0.2rem' }}>
                    <span className={`badge ${getOutcomeBadgeClass(inspectEvent.outcome)}`}>
                      {inspectEvent.outcome}
                    </span>
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Timestamp</div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                    {new Date(inspectEvent.timestamp).toLocaleString()}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Operator</div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                    {inspectEvent.operator ? `@${inspectEvent.operator}` : 'System Agent'}
                  </div>
                </div>
              </div>

              {inspectEvent.message && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Message</div>
                  <div style={{
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '0.75rem 1rem',
                    fontSize: '0.8125rem',
                    color: 'var(--text-primary)',
                  }}>
                    {inspectEvent.message}
                  </div>
                </div>
              )}

              {/* Related Resources */}
              <div style={{ marginBottom: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {inspectEvent.execution_id && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    Execution ID: {inspectEvent.execution_id}
                  </div>
                )}
                {inspectEvent.recovery_plan_id && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    Recovery Plan ID: {inspectEvent.recovery_plan_id}
                  </div>
                )}
              </div>

              {/* Sanitized Payload Details */}
              {inspectEvent.details && (
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                    Sanitized Payload Metadata
                  </div>
                  <pre style={{
                    background: 'rgba(0, 0, 0, 0.4)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '0.875rem',
                    fontSize: '0.75rem',
                    color: '#38bdf8',
                    overflowX: 'auto',
                  }}>
                    {JSON.stringify(inspectEvent.details, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            <div style={{ padding: '1rem 1.5rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setInspectEvent(null)} className="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

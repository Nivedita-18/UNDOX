import { useState } from "react";

import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  NavLink,
  Outlet,
  Link,
  useLocation,
  useNavigate
} from "react-router-dom";

import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bell,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileText,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Workflow,
  X,
  UserRound,
  RefreshCw,
  PlayCircle,
  Zap
} from "lucide-react";

import { useDashboard } from "./context/DashboardContext";
import { useAuth } from "./context/AuthContext";
import WorkflowCenter from "./pages/WorkflowCenter";
import ExecutionCenter from "./pages/ExecutionCenter";
import RecoveryCenter from "./pages/RecoveryCenter";
import AuditCenter from "./pages/AuditCenter";
import ProfileCenter from "./pages/ProfileCenter";

import "./App.css";


const navigation = [
  { label: "Overview", path: "/dashboard", icon: LayoutDashboard },
  { label: "Workflows", path: "/workflows", icon: Workflow },
  { label: "Executions", path: "/executions", icon: PlayCircle },
  { label: "Recovery Plans", path: "/recovery", icon: RefreshCw },
  { label: "Audit Logs", path: "/audit", icon: FileText }
];


function Sidebar({ mobileOpen, closeSidebar }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    closeSidebar();
    navigate("/login", { replace: true });
  }
  return (
    <>
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={closeSidebar} />
      )}

      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-icon">
            <Zap size={23} />
          </div>

          <div className="brand-text">
            <h2>UNDOX</h2>
            <span>WORKFLOW RECOVERY</span>
          </div>

          <button
            className="sidebar-close"
            onClick={closeSidebar}
            aria-label="Close navigation"
          >
            <X size={19} />
          </button>
        </div>

        <div className="workspace-selector">
          <div className="workspace-avatar">U</div>

          <div className="workspace-info">
            <strong>My Workspace</strong>
            <span>Personal workspace</span>
          </div>

          <ChevronDown size={16} />
        </div>

        <div className="nav-section">
          <span className="nav-heading">WORKSPACE</span>

          <nav className="sidebar-nav">
            {navigation.map((item) => {
              const Icon = item.icon;

              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === "/dashboard"}
                  onClick={closeSidebar}
                  className={({ isActive }) =>
                    `sidebar-link ${isActive ? "active" : ""}`
                  }
                >
                  <Icon size={19} />
                  <span>{item.label}</span>

                  {item.label === "Recovery Plans" && (
                    <span className="nav-indicator">!</span>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>

        <div className="sidebar-bottom">
          <div className="system-status">
            <span className="status-dot" />
            <div>
              <strong>System workspace</strong>
              <span>UNDOX development workspace</span>
            </div>
          </div>

          <NavLink
            to="/profile"
            onClick={closeSidebar}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? "active" : ""}`
            }
          >
            <UserRound size={19} />
            <span>My Profile</span>
          </NavLink>

          <button className="sidebar-link">
            <Settings size={19} />
            <span>Settings</span>
          </button>

          <button className="sidebar-link" onClick={handleLogout}>
            <LogOut size={19} />
            <span>Logout</span>
          </button>

          <button className="sidebar-link">
            <CircleHelp size={19} />
            <span>Help Center</span>
          </button>

          <div className="sidebar-user">
            <div className="user-avatar">
              {(user?.email || "U").charAt(0).toUpperCase()}
            </div>

            <div className="user-info">
              <strong>{user?.email || "Workspace User"}</strong>
              <span>{user?.role || "VIEWER"} Account</span>
            </div>

            <ChevronDown size={16} />
          </div>
        </div>
      </aside>
    </>
  );
}


function Topbar({ pageTitle, onMenuClick }) {
  const [notificationOpen, setNotificationOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="mobile-menu-button"
          onClick={onMenuClick}
          aria-label="Open navigation"
        >
          <Menu size={22} />
        </button>

        <div className="page-heading">
          <span className="breadcrumb">
            WORKSPACE
            <ChevronRight size={13} />
            {pageTitle.toUpperCase()}
          </span>

          <h1>{pageTitle}</h1>
        </div>
      </div>

      <div className="topbar-right">
        <div className="search-field">
          <Search size={17} />

          <input
            type="search"
            placeholder="Search workspace..."
            aria-label="Search workspace"
          />

          <kbd>⌘ K</kbd>
        </div>

        <div className="notification-wrapper">
          <button
            className="icon-button notification-button"
            onClick={() => setNotificationOpen(!notificationOpen)}
            aria-label="Notifications"
          >
            <Bell size={19} />
            <span className="notification-dot" />
          </button>

          {notificationOpen && (
            <div className="notification-popover">
              <strong>Notifications</strong>
              <p>
                Notifications will appear here as workflow events
                and recovery updates are integrated.
              </p>
            </div>
          )}
        </div>

        <button
          className="header-profile"
          onClick={() => navigate("/profile")}
          aria-label="Open profile"
        >
          <div className="header-avatar">U</div>
        </button>
      </div>
    </header>
  );
}


function PageTitle({ eyebrow, title, description, children }) {
  return (
    <div className="content-heading">
      <div>
        <span className="section-eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>

      {children && (
        <div className="heading-actions">
          {children}
        </div>
      )}
    </div>
  );
}


function MetricCard({
  label,
  value,
  description,
  icon: Icon,
  tone,
  metaLabel = "Live data pending"
}) {
  return (
    <article className="metric-card">
      <div className="metric-card-top">
        <span className={`metric-icon ${tone}`}>
          <Icon size={20} />
        </span>

        <span className="metric-placeholder">
          <ArrowUpRight size={15} />
          {metaLabel}
        </span>
      </div>

      <div className="metric-data">
        <span>{label}</span>
        <h3>{value}</h3>
        <p>{description}</p>
      </div>
    </article>
  );
}


function EmptyState({
  icon: Icon = FileText,
  title,
  description
}) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">
        <Icon size={28} />
      </div>

      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}


function formatActivityDate(value) {
  if (!value) {
    return "Date unavailable";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString();
}


function DashboardPage() {
  const {
    data,
    loading,
    error,
    refreshDashboard
  } = useDashboard();

  const metrics = data?.metrics || {};
  const activities = data?.auditEvents || [];

  const handleRefresh = () => {
    refreshDashboard().catch(() => {});
  };

  const dataStatus = loading
    ? "Refreshing dashboard data"
    : error
      ? "API data unavailable"
      : "Live API data connected";

  const metricMeta = loading
    ? "Loading..."
    : error
      ? "Unavailable"
      : "Live API data";

  return (
    <div className="page-container">

      <PageTitle
        eyebrow="OVERVIEW"
        title="Dashboard"
        description="Monitor your workflows, executions and recovery activity."
      />

      <div className="welcome-banner">
        <div className="welcome-content">
          <div className="welcome-label">
            <Zap size={15} />
            WORKFLOW INTELLIGENCE
          </div>

          <h2>
            Welcome to <span>UNDOX.</span>
          </h2>

          <p>
            Manage workflows, detect execution failures
            and coordinate recovery operations from
            one centralized workspace.
          </p>

          <Link to="/workflows" className="welcome-button">
            Explore Workflows
            <ArrowUpRight size={17} />
          </Link>
        </div>

        <div className="welcome-visual">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />

          <div className="orbit-center">
            <Zap size={38} />
          </div>

          <div className="floating-node node-one">
            <CheckCircle2 size={19} />
          </div>

          <div className="floating-node node-two">
            <RefreshCw size={19} />
          </div>

          <div className="floating-node node-three">
            <Activity size={19} />
          </div>
        </div>
      </div>

      <div className="section-title-row">
        <div>
          <h3>System Overview</h3>
          <p>Application performance indicators</p>
        </div>

        <div className="dashboard-toolbar">
          <span className="data-status">
            <span className="status-dot" />
            {dataStatus}
          </span>

          <button
            className="filter-button"
            onClick={handleRefresh}
            disabled={loading}
          >
            <RefreshCw size={16} />
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {error && (
        <div className="audit-info-banner dashboard-error">
          <AlertTriangle size={20} />

          <div>
            <strong>Unable to load dashboard information</strong>
            <p>{error}</p>
          </div>
        </div>
      )}

      <div className="metrics-grid">
        <MetricCard
          label="Total Workflows"
          value={loading ? "..." : error ? "—" : metrics.totalWorkflows ?? 0}
          description="Registered workflow definitions"
          icon={Workflow}
          tone="purple"
          metaLabel={metricMeta}
        />

        <MetricCard
          label="Total Executions"
          value={loading ? "..." : error ? "—" : metrics.totalExecutions ?? 0}
          description="Workflow execution attempts"
          icon={PlayCircle}
          tone="blue"
          metaLabel={metricMeta}
        />

        <MetricCard
          label="Failed Executions"
          value={loading ? "..." : error ? "—" : metrics.failedExecutions ?? 0}
          description="Executions requiring attention"
          icon={AlertTriangle}
          tone="red"
          metaLabel={metricMeta}
        />

        <MetricCard
          label="Recovery Plans"
          value={loading ? "..." : error ? "—" : metrics.totalRecoveryPlans ?? 0}
          description="Generated recovery operations"
          icon={RefreshCw}
          tone="green"
          metaLabel={metricMeta}
        />
      </div>

      <div className="dashboard-panels">

        <section className="dashboard-panel activity-panel">
          <div className="panel-heading">
            <div>
              <h3>Recent Activity</h3>
              <p>Latest workflow and recovery events</p>
            </div>

            <Link to="/audit" className="text-link">
              View All
              <ArrowUpRight size={15} />
            </Link>
          </div>

          {loading ? (
            <EmptyState
              icon={Activity}
              title="Loading activity"
              description="Fetching recent events from the backend."
            />
          ) : error ? (
            <EmptyState
              icon={AlertTriangle}
              title="Activity unavailable"
              description="Dashboard data could not be loaded."
            />
          ) : data?.auditAvailable === false ? (
            <EmptyState
              icon={ShieldCheck}
              title="Audit access unavailable"
              description="Audit history requires an ADMIN or OPERATOR account."
            />
          ) : activities.length === 0 ? (
            <EmptyState
              icon={Activity}
              title="No recent activity"
              description="Workflow, execution and recovery events will appear here when recorded."
            />
          ) : (
            <div className="activity-list">
              {activities.slice(0, 8).map((event, index) => {
                const eventName = String(
                  event.event_type || "System event"
                ).replaceAll("_", " ");

                return (
                  <article
                    className="activity-item"
                    key={event.id ?? `${event.event_type}-${index}`}
                  >
                    <div className="activity-icon">
                      <Activity size={18} />
                    </div>

                    <div className="activity-content">
                      <strong>
                        {eventName.charAt(0).toUpperCase() +
                          eventName.slice(1)}
                      </strong>

                      <p>
                        {event.message || "An application event was recorded."}
                      </p>

                      <span>
                        {formatActivityDate(event.created_at)}
                      </span>
                    </div>

                    <span className="activity-outcome">
                      {event.outcome || "RECORDED"}
                    </span>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className="dashboard-panel status-panel">
          <div className="panel-heading">
            <div>
              <h3>Execution Status</h3>
              <p>Workflow execution distribution</p>
            </div>
          </div>

          <div className="status-overview">
            <div className="status-overview-icon">
              <Activity size={25} />
            </div>

            <h2>
              {loading ? "..." : error ? "—" : metrics.totalExecutions ?? 0}
            </h2>

            <span>Total executions</span>
          </div>

          <div className="status-legend">
            <div>
              <span className="legend-dot completed" />
              Completed
              <strong>
                {loading ? "—" : metrics.completedExecutions ?? 0}
              </strong>
            </div>

            <div>
              <span className="legend-dot failed" />
              Failed
              <strong>
                {loading ? "—" : metrics.failedExecutions ?? 0}
              </strong>
            </div>

            <div>
              <span className="legend-dot pending" />
              Running / Pending
              <strong>
                {loading ? "—" : metrics.runningExecutions ?? 0}
              </strong>
            </div>
          </div>
        </section>
      </div>

      <section className="dashboard-panel quick-actions">
        <div className="panel-heading">
          <div>
            <h3>Quick Navigation</h3>
            <p>Access your main workspace modules</p>
          </div>
        </div>

        <div className="quick-action-grid">
          <Link to="/workflows" className="quick-action-card">
            <Workflow size={21} />
            <strong>Workflows</strong>
            <span>Manage definitions</span>
            <ChevronRight size={17} />
          </Link>

          <Link to="/executions" className="quick-action-card">
            <PlayCircle size={21} />
            <strong>Executions</strong>
            <span>Monitor execution history</span>
            <ChevronRight size={17} />
          </Link>

          <Link to="/recovery" className="quick-action-card">
            <RefreshCw size={21} />
            <strong>Recovery</strong>
            <span>Review recovery plans</span>
            <ChevronRight size={17} />
          </Link>

          <Link to="/audit" className="quick-action-card">
            <ShieldCheck size={21} />
            <strong>Audit Logs</strong>
            <span>Inspect system events</span>
            <ChevronRight size={17} />
          </Link>
        </div>
      </section>
    </div>
  );
}


// Workflows Page
function WorkflowsPage() {
  const navigate = useNavigate();

  return (
    <div className="page-container">
      <PageTitle
        eyebrow="WORKSPACE / AUTOMATION"
        title="Workflows"
        description="Create, organize and manage sequential business workflows."
      >
        <button
          className="primary-button"
          onClick={() => navigate("/workflows/new")}
        >
          <Plus size={18} />
          Create Workflow
        </button>
      </PageTitle>

      <div className="filter-toolbar">
        <div className="search-field table-search">
          <Search size={17} />
          <input
            placeholder="Search workflows..."
            aria-label="Search workflows"
          />
        </div>

        <button className="filter-button">
          <ListChecks size={17} />
          All Workflows
          <ChevronDown size={15} />
        </button>
      </div>

      <section className="dashboard-panel table-panel">
        <div className="panel-heading">
          <div>
            <h3>Workflow Registry</h3>
            <p>All registered workflow definitions</p>
          </div>
        </div>

        <div className="table-placeholder">
          <div className="table-header">
            <span>WORKFLOW</span>
            <span>STEPS</span>
            <span>STATUS</span>
            <span>CREATED</span>
            <span>ACTIONS</span>
          </div>

          <EmptyState
            icon={Workflow}
            title="Workflow integration in progress"
            description="Saved PostgreSQL workflows will appear here in the workflow integration phase."
          />
        </div>
      </section>
    </div>
  );
}


// Create Workflow Page
function CreateWorkflowPage() {
  const navigate = useNavigate();

  const [workflowName, setWorkflowName] = useState("");
  const [description, setDescription] = useState("");

  return (
    <div className="page-container">
      <PageTitle
        eyebrow="WORKFLOWS / NEW"
        title="Create Workflow"
        description="Define a new sequential workflow and its execution steps."
      />

      <section className="form-panel dashboard-panel">
        <div className="panel-heading">
          <div>
            <h3>Workflow Information</h3>
            <p>Enter the basic workflow details</p>
          </div>
        </div>

        <div className="form-content">
          <label className="form-label">
            Workflow Name

            <input
              className="form-input"
              value={workflowName}
              onChange={(event) => setWorkflowName(event.target.value)}
              placeholder="e.g. Order Fulfillment Workflow"
            />
          </label>

          <label className="form-label">
            Description

            <textarea
              className="form-input form-textarea"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Describe the purpose of this workflow..."
            />
          </label>

          <div className="integration-note">
            <Workflow size={20} />

            <div>
              <strong>Step Builder</strong>
              <p>
                Ordered steps, payload configuration and compensation
                settings will be implemented in the workflow builder phase.
              </p>
            </div>
          </div>

          <div className="form-actions">
            <button
              className="secondary-button"
              onClick={() => navigate("/workflows")}
            >
              Cancel
            </button>

            <button
              className="primary-button"
              disabled={!workflowName.trim()}
              title="Workflow API integration is pending"
              onClick={() =>
                alert("Workflow builder integration is coming next.")
              }
            >
              <Plus size={17} />
              Save Workflow
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}


// Executions Page
function ExecutionsPage() {
  return (
    <div className="page-container">
      <PageTitle
        eyebrow="WORKSPACE / MONITORING"
        title="Executions"
        description="Track workflow execution attempts and inspect step-level outcomes."
      />

      <div className="metrics-grid">
        <MetricCard
          label="Completed"
          value="—"
          description="Successful execution attempts"
          icon={CheckCircle2}
          tone="green"
        />

        <MetricCard
          label="Failed"
          value="—"
          description="Execution failures"
          icon={AlertTriangle}
          tone="red"
        />

        <MetricCard
          label="Running"
          value="—"
          description="Currently active executions"
          icon={Clock3}
          tone="blue"
        />

        <MetricCard
          label="Total"
          value="—"
          description="All recorded attempts"
          icon={Activity}
          tone="purple"
        />
      </div>

      <section className="dashboard-panel table-panel">
        <div className="panel-heading">
          <div>
            <h3>Execution History</h3>
            <p>Individual execution records and their outcomes</p>
          </div>
        </div>

        <EmptyState
          icon={PlayCircle}
          title="Execution integration in progress"
          description="Your completed and failed execution records will appear here after implementation."
        />
      </section>
    </div>
  );
}


// Recovery Page
function RecoveryPage() {
  return (
    <div className="page-container">
      <PageTitle
        eyebrow="WORKSPACE / FAILURE MANAGEMENT"
        title="Recovery Plans"
        description="Review recovery proposals, conflicts and approval decisions."
      />

      <section className="dashboard-panel table-panel">
        <div className="panel-heading">
          <div>
            <h3>Recovery Registry</h3>
            <p>Generated recovery plans and their lifecycle states</p>
          </div>
        </div>

        <EmptyState
          icon={RefreshCw}
          title="Recovery integration in progress"
          description="Generated, approved and executed recovery plans will appear here after implementation."
        />
      </section>
    </div>
  );
}


// Audit Page
function AuditPage() {
  return (
    <div className="page-container">
      <PageTitle
        eyebrow="WORKSPACE / SECURITY"
        title="Audit Logs"
        description="Inspect important workflow, execution and recovery events."
      />

      <div className="audit-info-banner">
        <ShieldCheck size={21} />

        <div>
          <strong>Audit History</strong>
          <p>
            Audit events are stored separately from workflow and recovery records.
          </p>
        </div>
      </div>

      <section className="dashboard-panel table-panel">
        <div className="panel-heading">
          <div>
            <h3>Event History</h3>
            <p>Chronological system activity</p>
          </div>
        </div>

        <EmptyState
          icon={FileText}
          title="Audit integration in progress"
          description="User activity, execution outcomes and recovery decisions will be displayed here."
        />
      </section>
    </div>
  );
}


// Profile Page
function ProfilePage() {
  return (
    <div className="page-container">
      <PageTitle
        eyebrow="ACCOUNT"
        title="My Profile"
        description="Your UNDOX workspace account information."
      />

      <section className="dashboard-panel profile-panel">
        <div className="profile-avatar">
          <UserRound size={34} />
        </div>

        <h3>Account Information</h3>

        <p>
          User profile information will be loaded through the authenticated /auth/me API.
        </p>

        <div className="profile-detail">
          <span>Email Address</span>
          <strong>Awaiting profile integration</strong>
        </div>

        <div className="profile-detail">
          <span>Account Role</span>
          <strong>Awaiting profile integration</strong>
        </div>

        <div className="profile-detail">
          <span>Account Status</span>
          <strong>Awaiting profile integration</strong>
        </div>
      </section>
    </div>
  );
}


// Dashboard Layout
function DashboardLayout() {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const currentPage =
    navigation.find((item) => item.path === location.pathname)?.label ||
    "Create Workflow";

  return (
    <div className="app-layout">
      <Sidebar
        mobileOpen={mobileOpen}
        closeSidebar={() => setMobileOpen(false)}
      />

      <div className="app-main">
        <Topbar
          pageTitle={currentPage}
          onMenuClick={() => setMobileOpen(true)}
        />

        <main className="main-content">
          <Outlet />
        </main>

        <footer className="app-footer">
          <span>© 2026 UNDOX Workflow Recovery System</span>
          <span className="footer-version">Development Workspace</span>
        </footer>
      </div>
    </div>
  );
}


// Main Application
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<Navigate to="/dashboard" replace />}
        />

        <Route element={<DashboardLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/workflows" element={<WorkflowCenter />} />
          <Route path="/workflows/new" element={<WorkflowCenter mode="create" />} />
          <Route path="/executions" element={<ExecutionCenter />} />
          <Route path="/recovery" element={<RecoveryCenter />} />
          <Route path="/audit" element={<AuditCenter />} />
          <Route path="/profile" element={<ProfileCenter />} />
        </Route>

        <Route
          path="*"
          element={<Navigate to="/dashboard" replace />}
        />
      </Routes>
    </BrowserRouter>
  );
}


export default App;

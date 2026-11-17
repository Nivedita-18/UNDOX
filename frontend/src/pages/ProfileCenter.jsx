import { useAuth } from "../context/AuthContext";

import {
  UserRound,
  Mail,
  ShieldCheck,
  CalendarDays,
  Fingerprint,
  CheckCircle2,
} from "lucide-react";

import "./ProfileCenter.css";


function formatDate(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "Not available"
    : date.toLocaleString();
}


export default function ProfileCenter() {
  const { user } = useAuth();

  const role = String(user?.role || "VIEWER").toUpperCase();

  const roleDescriptions = {
    ADMIN: "Full administrative access to the UNDOX workspace.",
    OPERATOR: "Can create workflows, execute operations and manage recovery.",
    VIEWER: "Read-only access to available workspace information.",
  };

  return (
    <div className="page-container profile-page">

      <div className="content-heading">
        <div>
          <span className="section-eyebrow">
            ACCOUNT / PERSONAL INFORMATION
          </span>

          <h2>My Profile</h2>

          <p>
            Manage and view your authenticated UNDOX account information.
          </p>
        </div>
      </div>


      <section className="dashboard-panel profile-overview-card">

        <div className="profile-cover">
          <div className="profile-avatar-large">
            <UserRound size={38} />
          </div>
        </div>

        <div className="profile-overview-content">

          <div>
            <h3>{user?.email || "Workspace User"}</h3>

            <p>
              UNDOX Workspace Account
            </p>
          </div>

          <span className="profile-active-badge">
            <span />
            {user?.is_active ? "Active Account" : "Inactive Account"}
          </span>

        </div>

      </section>


      <section className="dashboard-panel profile-details-panel">

        <div className="panel-heading">
          <div>
            <h3>Account Information</h3>
            <p>Your registered account details</p>
          </div>

          <ShieldCheck size={22} />
        </div>


        <div className="profile-information-grid">

          <div className="profile-information-item">
            <div className="profile-information-icon">
              <Fingerprint size={19} />
            </div>

            <div>
              <span>User ID</span>
              <strong>{user?.id ?? "Not available"}</strong>
            </div>
          </div>


          <div className="profile-information-item">
            <div className="profile-information-icon">
              <Mail size={19} />
            </div>

            <div>
              <span>Email Address</span>
              <strong>{user?.email || "Not available"}</strong>
            </div>
          </div>


          <div className="profile-information-item">
            <div className="profile-information-icon">
              <ShieldCheck size={19} />
            </div>

            <div>
              <span>Account Role</span>
              <strong>{role}</strong>
            </div>
          </div>


          <div className="profile-information-item">
            <div className="profile-information-icon">
              <CalendarDays size={19} />
            </div>

            <div>
              <span>Account Created</span>
              <strong>{formatDate(user?.created_at)}</strong>
            </div>
          </div>


          <div className="profile-information-item">
            <div className="profile-information-icon">
              <CheckCircle2 size={19} />
            </div>

            <div>
              <span>Account Status</span>
              <strong>
                {user?.is_active ? "Active" : "Inactive"}
              </strong>
            </div>
          </div>

        </div>

      </section>


      <section className="dashboard-panel profile-role-panel">

        <div className="panel-heading">
          <div>
            <h3>Role & Permissions</h3>
            <p>Access level associated with your account</p>
          </div>
        </div>

        <div className="profile-role-content">

          <div className="profile-role-badge">
            <ShieldCheck size={20} />
            {role}
          </div>

          <p>
            {roleDescriptions[role] ||
              "Access is determined by your assigned account role."}
          </p>

          <span>
            Permissions are enforced by the UNDOX backend.
          </span>

        </div>

      </section>

    </div>
  );
}

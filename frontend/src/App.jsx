import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import Toast from './components/Toast';
import AuthView from './views/AuthView';
import DashboardSummaryView from './views/DashboardSummaryView';
import WorkflowsView from './views/WorkflowsView';
import ExecutionsView from './views/ExecutionsView';
import RecoveryPlansView from './views/RecoveryPlansView';
import AuditLogsView from './views/AuditLogsView';

function DashboardApp() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [navParams, setNavParams] = useState({});
  const [toast, setToast] = useState(null);
  const [showAuthModal, setShowAuthModal] = useState(false);

  const showToast = (message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 4500);
  };

  const handleNavigate = (tab, params = {}) => {
    setNavParams(params);
    setActiveTab(tab);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        activeTab={activeTab}
        setActiveTab={(tab) => {
          setNavParams({});
          setActiveTab(tab);
        }}
        onOpenAuthModal={() => setShowAuthModal(true)}
      />

      <main style={{ flex: 1 }}>
        {activeTab === 'dashboard' && (
          <DashboardSummaryView onNavigate={handleNavigate} showToast={showToast} />
        )}
        {activeTab === 'workflows' && (
          <WorkflowsView onNavigate={handleNavigate} showToast={showToast} />
        )}
        {activeTab === 'executions' && (
          <ExecutionsView
            initialExecutionId={navParams.selectedExecutionId}
            onNavigate={handleNavigate}
            showToast={showToast}
          />
        )}
        {activeTab === 'recovery' && (
          <RecoveryPlansView
            initialPlanId={navParams.selectedPlanId}
            onNavigate={handleNavigate}
            showToast={showToast}
          />
        )}
        {activeTab === 'audit' && (
          <AuditLogsView showToast={showToast} />
        )}
      </main>

      {/* Auth Modal */}
      {showAuthModal && (
        <AuthView
          onClose={() => setShowAuthModal(false)}
          onSuccess={(msg) => showToast(msg, 'success')}
        />
      )}

      {/* Toast Alert */}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <DashboardApp />
    </AuthProvider>
  );
}

import { BrowserRouter, Routes, Route } from "react-router-dom";

import { useAuth } from "./context/AuthContext";
import { DashboardProvider } from "./context/DashboardContext";

import App from "./App";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";

function AuthLoadingScreen() {
  return (
    <div className="auth-loading">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="auth-brand-icon">
            UNDOX
          </div>
        </div>

        <h2>Restoring your session...</h2>

        <p>Please wait while your account is being verified.</p>
      </div>
    </div>
  );
}

export default function AppGate() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <AuthLoadingScreen />;
  }

  if (isAuthenticated) {
    return (
      <DashboardProvider>
        <App />
      </DashboardProvider>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="*" element={<LoginPage />} />
      </Routes>
    </BrowserRouter>
  );
}

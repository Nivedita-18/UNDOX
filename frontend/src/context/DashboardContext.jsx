import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { getDashboardData } from "../services/dashboardService";

const DashboardContext = createContext(null);

export function DashboardProvider({ children }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshDashboard = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const result = await getDashboardData();
      setData(result);
      return result;
    } catch (err) {
      const detail = err.response?.data?.detail;

      const message =
        typeof detail === "string"
          ? detail
          : err.message || "Unable to load dashboard data.";

      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshDashboard().catch(() => {});
  }, [refreshDashboard]);

  const value = useMemo(
    () => ({
      data,
      loading,
      error,
      refreshDashboard,
    }),
    [data, loading, error, refreshDashboard]
  );

  return (
    <DashboardContext.Provider value={value}>
      {children}
    </DashboardContext.Provider>
  );
}

export function useDashboard() {
  const context = useContext(DashboardContext);

  if (!context) {
    throw new Error(
      "useDashboard must be used inside DashboardProvider."
    );
  }

  return context;
}

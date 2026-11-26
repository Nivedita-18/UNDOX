import axios from "axios";

const TOKEN_KEY = "undox_access_token";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 15000,
  headers: {
    Accept: "application/json",
  },
});

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token) {
  if (!token) {
    throw new Error("A valid access token is required.");
  }

  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken() {
  localStorage.removeItem(TOKEN_KEY);
}

apiClient.interceptors.request.use(
  (config) => {
    const token = getAccessToken();

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    } else {
      delete config.headers.Authorization;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      clearAccessToken();
      if (typeof window !== "undefined" && !window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;

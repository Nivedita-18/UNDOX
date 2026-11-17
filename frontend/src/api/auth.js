import apiClient, {
  setAccessToken,
  clearAccessToken,
} from "./client";

export async function registerUser(userData) {
  const response = await apiClient.post("/auth/register", {
    email: userData.email,
    password: userData.password,
  });

  return response.data;
}

export async function loginUser(credentials) {
  const response = await apiClient.post("/auth/login", {
    email: credentials.email,
    password: credentials.password,
  });

  const token = response.data?.access_token;

  if (!token) {
    throw new Error("Login response does not contain an access token.");
  }

  setAccessToken(token);

  return response.data;
}

export async function getCurrentUser() {
  const response = await apiClient.get("/auth/me");
  return response.data;
}

export function logoutUser() {
  clearAccessToken();
}

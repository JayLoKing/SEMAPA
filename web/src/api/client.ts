import axios from "axios";
import { useAuthStore } from "../store/auth";

const baseURL =
  (import.meta as any).env?.VITE_API_URL || "/api/v1";

export const api = axios.create({
  baseURL,
  timeout: 30_000,
});

api.interceptors.request.use((cfg) => {
  const t = useAuthStore.getState().token;
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

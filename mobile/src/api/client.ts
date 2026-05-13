import axios from "axios";
import { useAuthStore } from "../store/auth";

const baseURL = process.env.EXPO_PUBLIC_API_URL || "http://10.0.2.2/api/v1";
// Android emulator: 10.0.2.2 → host
// iOS simulator: localhost
// Dispositivo físico: IP local del backend

export const api = axios.create({ baseURL, timeout: 30000 });

api.interceptors.request.use(async (cfg) => {
  const t = useAuthStore.getState().token;
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

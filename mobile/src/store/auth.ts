import { create } from "zustand";
import * as SecureStore from "expo-secure-store";

interface AuthState {
  token: string | null;
  rol: string | null;
  nombre: string | null;
  hydrate: () => Promise<void>;
  login: (token: string, rol: string, nombre: string) => Promise<void>;
  logout: () => Promise<void>;
}

const KEY = "semapa-token";

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  rol: null,
  nombre: null,
  async hydrate() {
    const raw = await SecureStore.getItemAsync(KEY);
    if (raw) {
      try {
        const { token, rol, nombre } = JSON.parse(raw);
        set({ token, rol, nombre });
      } catch {}
    }
  },
  async login(token, rol, nombre) {
    await SecureStore.setItemAsync(KEY, JSON.stringify({ token, rol, nombre }));
    set({ token, rol, nombre });
  },
  async logout() {
    await SecureStore.deleteItemAsync(KEY);
    set({ token: null, rol: null, nombre: null });
  },
}));

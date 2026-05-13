import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Rol = "ALCALDIA" | "GERENCIA" | "CONTABILIDAD";

interface AuthState {
  token: string | null;
  rol: Rol | null;
  nombre: string | null;
  login: (token: string, rol: Rol, nombre: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      rol: null,
      nombre: null,
      login: (token, rol, nombre) => set({ token, rol, nombre }),
      logout: () => set({ token: null, rol: null, nombre: null }),
    }),
    { name: "semapa-auth" }
  )
);

import { create } from "zustand";

type Theme = "light" | "dark";

function apply(theme: Theme) {
  const root = document.documentElement;
  if (theme === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
  localStorage.setItem("semapa-theme", theme);
}

const initial: Theme =
  (localStorage.getItem("semapa-theme") as Theme) ||
  (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light");

apply(initial);

interface ThemeState {
  theme: Theme;
  toggle: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: initial,
  toggle: () => {
    const next: Theme = get().theme === "dark" ? "light" : "dark";
    apply(next);
    set({ theme: next });
  },
}));

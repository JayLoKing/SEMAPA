/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        semapa: {
          50:  "#eff8ff",
          100: "#deeefb",
          200: "#b6e0fe",
          500: "#0d6efd",
          600: "#0a58ca",
          700: "#084298",
          900: "#062260",
        },
        ink: {
          900: "#0b1220",
          800: "#111a2e",
          700: "#1b2740",
          600: "#26344f",
        },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255,255,255,.06), 0 8px 30px rgba(2,8,23,.45)",
      },
    },
  },
  plugins: [],
};

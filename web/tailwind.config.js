/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        semapa: {
          50:  "#eff8ff",
          100: "#deeefb",
          500: "#0d6efd",
          600: "#0a58ca",
          700: "#084298",
          900: "#062260",
        },
      },
    },
  },
  plugins: [],
};

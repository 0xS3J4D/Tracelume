/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        ink: { 950: "#0b1220", 900: "#0f172a", 850: "#131c2e", 800: "#1a2438", 700: "#26324a" },
        accent: { DEFAULT: "#2dd4bf", strong: "#14b8a6" },
        mark: "#f59e0b",
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};

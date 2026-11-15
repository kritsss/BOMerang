/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#12151C", ground: "#F4F5F7", line: "#E5E7EB", muted: "#5B6270", soft: "#F1F2F4",
        ai: { DEFAULT: "#6D28D9", bg: "#EDE9FE", line: "#DDD6FE" },
        human: { DEFAULT: "#0F766E", bg: "#CCFBF1", line: "#99F6E4" },
        save: { DEFAULT: "#1D4ED8", bg: "#DBEAFE" },
        navy: "#1E3A8A",
        cost: { DEFAULT: "#C2410C", bg: "#FFF7ED", line: "#FED7AA" },
        rule: { DEFAULT: "#4B5563", bg: "#E5E7EB" },
        ok: { DEFAULT: "#15803D", bg: "#DCFCE7" },
        warn: { DEFAULT: "#B45309", bg: "#FEF3C7" },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: { card: "16px" },
    },
  },
  plugins: [],
};

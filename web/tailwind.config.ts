import type { Config } from "tailwindcss";

export default {
  content: [
    "./app.vue",
    "./components/**/*.vue",
    "./layouts/**/*.vue",
    "./pages/**/*.vue",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#12140f",
        moss: "#5b7a3a",
        copper: "#c48a3a",
        stone: "#2a2e24",
        parchment: "#e7e1c9",
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "Segoe UI", "sans-serif"],
        display: ["IBM Plex Serif", "Georgia", "serif"],
      },
    },
  },
} satisfies Config;

import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dark research terminal palette (Section 4.2)
        bg: "#06111F",          // Background color
        navy: "#0E2238",        // Card background
        line: "#1F3550",        // Border color
        ink: "#E6EDF7",         // Primary text
        subink: "#8FA3BF",      // Secondary text
        weak: "#5F728A",        // Weak text
        
        // State colors
        ok: "#35D06E",          // Pass / Normal / Gain
        warn: "#F6B73C",        // Warning / Med Risk
        danger: "#FF5C5C",      // Fail / High Risk / Drawdown
        brand: "#3D7BFF",       // Info / Clickable
        neutral: "#9AA8BD",     // Reference / Neutral
        
        // Keep compatibility aliases
        cardline: "#1F3550",    // Border color
        songshi: "#35D06E",     // Green
        qielan: "#3D7BFF",      // Blue
        taishi: "#F6B73C",      // Yellow
      },
      borderRadius: { card: "12px" },
    },
  },
  plugins: [],
};

export default config;

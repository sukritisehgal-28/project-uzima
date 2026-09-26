export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], mono: ["'JetBrains Mono'", "ui-monospace", "monospace"] },
      colors: {
        ink: { bg: "#0B0D10", panel: "#111418", raised: "#171B21", line: "#23272E", text: "#E6E8EB", muted: "#8A919B", faint: "#5C636D" },
        brand: "#E0592A",
        st: { calling: "#D9A441", yes: "#3FB67A", no: "#D65A55", none: "#6B7280", released: "#4B5563" },
      },
    },
  },
  plugins: [],
};

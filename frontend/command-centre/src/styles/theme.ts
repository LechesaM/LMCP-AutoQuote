export const commandCentreTheme = {
  brand: {
    name: "LMCP",
    title: "Command Centre",
    position: "AI-Governed Procurement Operations Platform",
  },
  colors: {
    background: "#020617",
    backgroundAlt: "#08111f",
    panel: "rgba(15, 23, 42, 0.86)",
    panelSoft: "rgba(2, 6, 23, 0.72)",
    border: "rgba(148, 163, 184, 0.16)",
    text: "#e5eefb",
    muted: "#94a3b8",
    green: "#22c55e",
    cyan: "#22d3ee",
    amber: "#f59e0b",
    red: "#ef4444",
    telemetry: {
      low: "#38bdf8",
      moderate: "#22c55e",
      elevated: "#eab308",
      hot: "#f97316",
      critical: "#ef4444",
    },
  },
  spacing: {
    xs: "0.25rem",
    sm: "0.5rem",
    md: "1rem",
    lg: "1.5rem",
    xl: "2rem",
    "2xl": "3rem",
    "3xl": "4rem",
  },
  radius: {
    sm: "0.75rem",
    md: "1rem",
    lg: "1.25rem",
    xl: "1.5rem",
    "2xl": "1.75rem",
    "3xl": "2rem",
  },
  typography: {
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    display: {
      size: "2.5rem",
      weight: 900,
      letterSpacing: "-0.03em",
    },
    title: {
      size: "1.25rem",
      weight: 900,
      letterSpacing: "-0.02em",
    },
    label: {
      size: "0.75rem",
      weight: 800,
      letterSpacing: "0.22em",
      transform: "uppercase",
    },
  },
  shadows: {
    glass: "0 24px 80px rgba(0, 0, 0, 0.34)",
    glow: "0 0 28px rgba(34, 197, 94, 0.32)",
    cyanGlow: "0 0 28px rgba(34, 211, 238, 0.28)",
    elevated: "20px 0 80px rgba(0, 0, 0, 0.45)",
  },
  layout: {
    sidebarWidth: 290,
    minViewportWidth: 1280,
  },
};

export function applyCommandCentreThemeVars(target = document.documentElement) {
  if (!target) {
    return;
  }

  const style = target.style;
  style.setProperty("--cc-bg", commandCentreTheme.colors.background);
  style.setProperty("--cc-bg-alt", commandCentreTheme.colors.backgroundAlt);
  style.setProperty("--cc-panel", commandCentreTheme.colors.panel);
  style.setProperty("--cc-panel-soft", commandCentreTheme.colors.panelSoft);
  style.setProperty("--cc-border", commandCentreTheme.colors.border);
  style.setProperty("--cc-text", commandCentreTheme.colors.text);
  style.setProperty("--cc-muted", commandCentreTheme.colors.muted);
  style.setProperty("--cc-green", commandCentreTheme.colors.green);
  style.setProperty("--cc-cyan", commandCentreTheme.colors.cyan);
  style.setProperty("--cc-amber", commandCentreTheme.colors.amber);
  style.setProperty("--cc-red", commandCentreTheme.colors.red);
  style.setProperty("--cc-telemetry-low", commandCentreTheme.colors.telemetry.low);
  style.setProperty("--cc-telemetry-moderate", commandCentreTheme.colors.telemetry.moderate);
  style.setProperty("--cc-telemetry-elevated", commandCentreTheme.colors.telemetry.elevated);
  style.setProperty("--cc-telemetry-hot", commandCentreTheme.colors.telemetry.hot);
  style.setProperty("--cc-telemetry-critical", commandCentreTheme.colors.telemetry.critical);
  style.setProperty("--cc-sidebar-width", `${commandCentreTheme.layout.sidebarWidth}px`);
  style.setProperty("--cc-font-family", commandCentreTheme.typography.fontFamily);
  style.setProperty("--cc-display-size", commandCentreTheme.typography.display.size);
  style.setProperty("--cc-display-weight", String(commandCentreTheme.typography.display.weight));
  style.setProperty("--cc-title-size", commandCentreTheme.typography.title.size);
  style.setProperty("--cc-title-weight", String(commandCentreTheme.typography.title.weight));
  style.setProperty("--cc-label-size", commandCentreTheme.typography.label.size);
  style.setProperty("--cc-label-weight", String(commandCentreTheme.typography.label.weight));
  style.setProperty("--cc-glass-shadow", commandCentreTheme.shadows.glass);
  style.setProperty("--cc-glow-shadow", commandCentreTheme.shadows.glow);
  style.setProperty("--cc-cyan-glow-shadow", commandCentreTheme.shadows.cyanGlow);
  style.setProperty("--cc-elevated-shadow", commandCentreTheme.shadows.elevated);
}

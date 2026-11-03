// Categorical palette for artifact types (distinguishable on dark backgrounds).
const PALETTE: Record<string, string> = {
  message: "#2dd4bf", call: "#60a5fa", contact: "#a78bfa", location: "#f59e0b",
  media: "#f472b6", web_history: "#34d399", app_usage: "#fbbf24", account: "#c084fc",
  file_entry: "#94a3b8", process: "#f87171", network_connection: "#38bdf8",
  registry: "#fb923c", log_event: "#a3e635", event: "#64748b",
};
export const typeColor = (t: string) => PALETTE[t] ?? "#64748b";

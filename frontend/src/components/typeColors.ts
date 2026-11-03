// Categorical palette for artifact types (distinguishable on dark backgrounds) and readable labels.
const PALETTE: Record<string, string> = {
  message: "#2dd4bf", call: "#60a5fa", contact: "#a78bfa", location: "#f59e0b",
  media: "#f472b6", web_history: "#34d399", app_usage: "#fbbf24", account: "#c084fc",
  file_entry: "#94a3b8", process: "#f87171", network_connection: "#38bdf8",
  registry: "#fb923c", log_event: "#a3e635", database: "#67e8f9",
  recovered_record: "#fb7185", event: "#64748b",
};
const LABELS: Record<string, string> = {
  message: "Messages", call: "Calls", contact: "Contacts", location: "Locations",
  media: "Photos & videos", web_history: "Web history", app_usage: "App usage",
  account: "Accounts", file_entry: "Files", process: "Processes",
  network_connection: "Network connections", registry: "Registry", log_event: "Event logs",
  database: "Databases", recovered_record: "Recovered (deleted) records", event: "Other events",
};
export const typeColor = (t: string) => PALETTE[t] ?? "#64748b";
export const typeLabel = (t: string) => LABELS[t] ?? t;

/** Heuristics to read common fields from heterogeneous tool rows. */
const pick = (data: Record<string, unknown>, keys: string[]): string | undefined => {
  const lower = Object.fromEntries(Object.entries(data).map(([k, v]) => [k.toLowerCase(), v]));
  for (const k of keys) {
    const v = lower[k.toLowerCase()];
    if (v !== undefined && v !== null && String(v).trim() !== "") return String(v);
  }
  return undefined;
};

export const counterpart = (d: Record<string, unknown>) =>
  pick(d, ["Address", "Handle", "Phone Number", "Number", "Contact", "Participant", "Chat",
    "Thread ID", "Conversation", "From", "To"]) ?? "Unknown";

export const body = (d: Record<string, unknown>) =>
  pick(d, ["Body", "Message", "Text", "Content", "Snippet"]) ?? "";

export const isOutgoing = (d: Record<string, unknown>) =>
  /\b(sent|outgoing|outbox|from me|is_from_me|1)\b/i.test(pick(d, ["Type", "Direction", "Is From Me", "Folder"]) ?? "");

export const latLon = (d: Record<string, unknown>): [number, number] | null => {
  const lat = Number(pick(d, ["Latitude", "Lat", "latitude"]));
  const lon = Number(pick(d, ["Longitude", "Lon", "Lng", "Long", "longitude"]));
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  if (lat === 0 && lon === 0) return null;
  return [lat, lon];
};

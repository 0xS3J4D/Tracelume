export type EvidenceKind =
  | "disk_image" | "android_fs" | "ios_backup" | "ios_fs" | "memory_image" | "windows_triage" | "logs" | "other";

export const EVIDENCE_KINDS: { value: EvidenceKind; label: string }[] = [
  { value: "android_fs", label: "Android file system / backup" },
  { value: "ios_backup", label: "iOS backup" },
  { value: "ios_fs", label: "iOS file system" },
  { value: "disk_image", label: "Disk image" },
  { value: "memory_image", label: "Memory image" },
  { value: "windows_triage", label: "Windows triage collection (KAPE / Velociraptor .zip)" },
  { value: "logs", label: "Logs" },
  { value: "other", label: "Other" },
];

export interface Case {
  id: string; name: string; number: string | null; description: string | null;
  examiner: string; status: string; created_at: string;
}
export interface CaseSummary {
  case: Case; evidence_count: number; job_count: number; artifact_counts: Record<string, number>;
}
export interface Evidence {
  id: string; case_id: string; kind: EvidenceKind; original_filename: string; size: number;
  sha256: string; md5: string; acquired_by: string | null; notes: string | null;
  ingested_at: string; last_verified_at: string | null; verify_status: string;
}
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export interface Job {
  id: string; case_id: string; evidence_id: string | null; plugin: string; plugin_version: string;
  status: JobStatus; created_at: string; started_at: string | null; finished_at: string | null;
  exit_code: number | null; artifact_count: number; error: string | null;
  params: Record<string, unknown>;
}
export interface Artifact {
  id: string; case_id: string; evidence_id: string; job_id: string; type: string;
  timestamp: string | null; timestamp_kind: string | null; source_plugin: string;
  source_path: string | null; title: string; data: Record<string, unknown>;
}
export interface PluginInfo {
  name: string; version: string; description: string; tool_name: string; tool_version: string;
  tool_license: string; tool_url: string; supported_evidence: EvidenceKind[];
  params_schema: Record<string, { type: "text" | "string"; label: string; required?: boolean; placeholder?: string }>;
}
export interface AuditEntry {
  id: number; ts: string; actor: string; action: string; object_type: string | null;
  object_id: string | null; details: Record<string, unknown>; hash_before: string | null;
  hash_after: string | null; entry_hash: string;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail ?? msg; } catch { /* not JSON */ }
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return res.json() as Promise<T>;
}
const json = (method: string, body: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

export interface Tag { id: string; case_id: string; name: string; color: string; count?: number }
export interface Note {
  id: string; case_id: string; artifact_id: string | null; author: string; body: string; created_at: string;
}
export interface Bucket { start: string; end: string; count: number; by_type: Record<string, number> }
export interface Histogram { min: string | null; max: string | null; buckets: Bucket[] }
export interface SearchHit { artifact: Artifact; case_name: string }
export type ArtifactQuery = {
  type?: string[]; plugin?: string[]; q?: string; tag?: string; since?: string; until?: string;
  order?: "asc" | "desc"; limit?: number; offset?: number; buckets?: number;
};

function qs(params: ArtifactQuery | Record<string, unknown>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === "" || v === null) continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, String(x)));
    else p.set(k, String(v));
  }
  return p.toString();
}

export interface DbInfo {
  id: string; path: string; sha256: string; size: number;
  tables: Record<string, number | null>; recovered: Record<string, number>;
}
export interface DbTable {
  name: string; type: string; sql: string | null; rows: number | null;
  columns: { name: string; type: string; pk: boolean }[];
}
export interface QueryResult { columns: string[]; rows: unknown[][]; truncated: boolean; elapsed_ms: number }

export interface AssistantStep { tool: string; args: Record<string, unknown>; result: unknown }
export interface AssistantMessage {
  id: string; role: "user" | "assistant"; content: string; steps: AssistantStep[];
  citations: string[]; model: string | null; author: string; created_at: string;
}
export interface AssistantPolicy { allow_remote: boolean; endpoint_local: boolean; model: string; enabled: boolean }
export interface Settings {
  assistant: { enabled: boolean; base_url: string; model: string; api_key: string; temperature: number; local: boolean };
  examiner: { name: string };
}

export interface BackupInfo { name: string; size: number; created: string; sha256: string | null }
export interface BackupState {
  status: { running: boolean; error: string | null; last: { name: string } | null };
  backups: BackupInfo[]; folder: string;
}

export const api = {
  cases: () => req<Case[]>("/cases"),
  createCase: (b: { name: string; number?: string; description?: string }) =>
    req<Case>("/cases", json("POST", b)),
  caseSummary: (id: string) => req<CaseSummary>(`/cases/${id}`),
  updateCase: (id: string, b: Partial<Pick<Case, "name" | "number" | "description" | "status">>) =>
    req<Case>(`/cases/${id}`, json("PATCH", b)),
  evidence: (caseId: string) => req<Evidence[]>(`/cases/${caseId}/evidence`),
  importFolder: () => req<{ path: string; size: number }[]>("/import"),
  importEvidence: (caseId: string, b: { path: string; kind: EvidenceKind; acquired_by?: string; notes?: string }) =>
    req<Evidence>(`/cases/${caseId}/evidence/import`, json("POST", b)),
  verify: (id: string) => req<Evidence>(`/evidence/${id}/verify`, { method: "POST" }),
  plugins: () => req<PluginInfo[]>("/plugins"),
  jobs: (caseId: string) => req<Job[]>(`/cases/${caseId}/jobs`),
  job: (id: string) => req<Job>(`/jobs/${id}`),
  createJob: (caseId: string, evidence_id: string, plugin: string, params: Record<string, string> = {}) =>
    req<Job>(`/cases/${caseId}/jobs`, json("POST", { evidence_id, plugin, params })),
  artifacts: (caseId: string, params: ArtifactQuery) =>
    req<{ total: number; items: Artifact[] }>(`/cases/${caseId}/artifacts?${qs(params)}`),
  artifact: (id: string) => req<Artifact>(`/artifacts/${id}`),
  histogram: (caseId: string, params: ArtifactQuery) =>
    req<Histogram>(`/cases/${caseId}/timeline/histogram?${qs(params)}`),
  search: (q: string) => req<SearchHit[]>(`/search?${qs({ q, limit: 30 })}`),
  tags: (caseId: string) => req<Tag[]>(`/cases/${caseId}/tags`),
  createTag: (caseId: string, name: string, color?: string) =>
    req<Tag>(`/cases/${caseId}/tags`, json("POST", { name, color })),
  artifactTags: (id: string) => req<Tag[]>(`/artifacts/${id}/tags`),
  tagArtifact: (id: string, tagId: string) =>
    fetch(`/api/artifacts/${id}/tags/${tagId}`, { method: "PUT" }),
  untagArtifact: (id: string, tagId: string) =>
    fetch(`/api/artifacts/${id}/tags/${tagId}`, { method: "DELETE" }),
  databases: (caseId: string) => req<DbInfo[]>(`/cases/${caseId}/databases`),
  dbSchema: (caseId: string, dbId: string) =>
    req<DbTable[]>(`/cases/${caseId}/databases/${encodeURIComponent(dbId)}/schema`),
  dbQuery: (caseId: string, dbId: string, sql: string) =>
    req<QueryResult>(`/cases/${caseId}/databases/${encodeURIComponent(dbId)}/query`, json("POST", { sql })),
  settings: () => req<Settings>("/settings"),
  saveAssistant: (b: Partial<Settings["assistant"]>) => req<Settings["assistant"]>("/settings/assistant", json("PUT", b)),
  saveExaminer: (name: string) => req<{ name: string }>("/settings/examiner", json("PUT", { name })),
  testAssistant: () => req<{ ok: boolean; reply?: string; error?: string }>("/settings/assistant/test", { method: "POST" }),
  policy: (caseId: string) => req<AssistantPolicy>(`/cases/${caseId}/assistant/policy`),
  setPolicy: (caseId: string, allow_remote: boolean) =>
    req<AssistantPolicy>(`/cases/${caseId}/assistant/policy`, json("PUT", { allow_remote })),
  assistantMessages: (caseId: string) => req<AssistantMessage[]>(`/cases/${caseId}/assistant/messages`),
  ask: (caseId: string, question: string) =>
    req<AssistantMessage>(`/cases/${caseId}/assistant`, json("POST", { question })),
  recover: (artifactId: string) => req<Job>(`/artifacts/${artifactId}/recover`, { method: "POST" }),
  cancelJob: (jobId: string) => req<Job>(`/jobs/${jobId}/cancel`, { method: "POST" }),
  backups: () => req<BackupState>("/backups"),
  createBackup: () => req<{ started: boolean }>("/backups", { method: "POST" }),
  acquireStatus: () => req<{ usb_available: boolean }>("/acquire/status"),
  acquireIos: (caseId: string, mode: "list" | "backup", udid?: string) =>
    req<Job>(`/cases/${caseId}/acquire/ios`, json("POST", { mode, udid })),
  acquireDevices: (jobId: string) =>
    req<{ udid: string; DeviceName?: string; ProductType?: string; ProductVersion?: string; paired?: boolean }[]>(`/jobs/${jobId}/devices`),
  notes: (caseId: string, artifactId?: string) =>
    req<Note[]>(`/cases/${caseId}/notes?${qs({ artifact_id: artifactId })}`),
  createNote: (caseId: string, body: string, artifactId?: string) =>
    req<Note>(`/cases/${caseId}/notes`, json("POST", { body, artifact_id: artifactId })),
  audit: (caseId: string) => req<AuditEntry[]>(`/cases/${caseId}/audit`),
};

/** Upload with progress (fetch has no upload progress events). */
export function uploadEvidence(
  caseId: string, form: FormData, onProgress: (sent: number, total: number) => void,
): Promise<Evidence> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/cases/${caseId}/evidence`);
    xhr.upload.onprogress = (e) => onProgress(e.loaded, e.total);
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
      else reject(new Error(xhr.responseText || xhr.statusText));
    };
    xhr.onerror = () => reject(new Error("upload failed"));
    xhr.send(form);
  });
}

export const fmtBytes = (n: number) => {
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
};
/** Analysts work in UTC; always show the zone explicitly. */
export const fmtUtc = (iso: string | null) =>
  iso ? new Date(iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z")
    .toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC") : "—";

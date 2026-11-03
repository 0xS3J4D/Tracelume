import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtBytes, fmtUtc, type Artifact, type Note, type Tag } from "../api";
import { typeLabel } from "./typeColors";

/** Right-hand detail panel: provenance, tags, notes and raw data. */
export default function ArtifactDetail({
  artifact, caseTags, onTagsChanged, focus,
}: {
  artifact: Artifact | undefined;
  caseTags: Tag[];
  onTagsChanged: () => void;
  focus?: { kind: "tag" | "note"; n: number };
}) {
  const [tags, setTags] = useState<Tag[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [newTag, setNewTag] = useState("");
  const [note, setNote] = useState("");
  const tagRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const id = artifact?.id;

  useEffect(() => {
    if (!id || !artifact) return;
    api.artifactTags(id).then(setTags);
    api.notes(artifact.case_id, id).then(setNotes);
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!focus) return;
    (focus.kind === "tag" ? tagRef : noteRef).current?.focus();
  }, [focus]);

  if (!artifact) return <p className="p-4 text-sm text-slate-400">Select an artifact.</p>;

  const toggle = async (t: Tag) => {
    if (tags.some((x) => x.id === t.id)) await api.untagArtifact(artifact.id, t.id);
    else await api.tagArtifact(artifact.id, t.id);
    setTags(await api.artifactTags(artifact.id));
    onTagsChanged();
  };
  const addTag = async (e: FormEvent) => {
    e.preventDefault();
    const name = newTag.trim();
    if (!name) return;
    const t = caseTags.find((x) => x.name.toLowerCase() === name.toLowerCase())
      ?? await api.createTag(artifact.case_id, name);
    if (!tags.some((x) => x.id === t.id)) await api.tagArtifact(artifact.id, t.id);
    setNewTag("");
    setTags(await api.artifactTags(artifact.id));
    onTagsChanged();
  };
  const addNote = async (e: FormEvent) => {
    e.preventDefault();
    if (!note.trim()) return;
    await api.createNote(artifact.case_id, note, artifact.id);
    setNote("");
    setNotes(await api.notes(artifact.case_id, artifact.id));
  };

  return (
    <div className="space-y-5 p-4">
      <div>
        <p className="label">{typeLabel(artifact.type)}</p>
        <h2 className="break-words font-medium text-slate-100">{artifact.title}</h2>
      </div>
      <dl className="grid grid-cols-[6rem_1fr] gap-x-2 gap-y-1 text-xs">
        <dt className="text-slate-400">Time</dt><dd className="font-mono">{fmtUtc(artifact.timestamp)}</dd>
        <dt className="text-slate-400">Time field</dt><dd>{artifact.timestamp_kind ?? "—"}</dd>
        <dt className="text-slate-400">Plugin</dt><dd>{artifact.source_plugin}</dd>
        <dt className="text-slate-400">Source path</dt><dd className="break-all font-mono">{artifact.source_path ?? "—"}</dd>
        <dt className="text-slate-400">Artifact ID</dt><dd className="break-all font-mono text-slate-500">{artifact.id}</dd>
      </dl>

      {Array.isArray(artifact.data.possible_times_utc) && artifact.data.possible_times_utc.length > 0 && (
        <div className="rounded-md border border-ink-700 p-3 text-xs">
          <p className="mb-1 text-slate-400">Values that decode as plausible timestamps (verify the unit in the app's schema):</p>
          <ul className="space-y-0.5 font-mono">
            {(artifact.data.possible_times_utc as { column: number; unit: string; utc: string }[]).map((t, i) => (
              <li key={i}>col {t.column}: {fmtUtc(t.utc)} <span className="text-slate-500">({t.unit})</span></li>
            ))}
          </ul>
        </div>
      )}
      {artifact.type === "media" && typeof artifact.data.thumb === "string" && (
        <img src={`/api/jobs/${artifact.job_id}/thumbs/${artifact.data.thumb}`} alt={artifact.title}
          className="max-h-72 w-full rounded-md border border-ink-700 bg-ink-950 object-contain" />
      )}
      {artifact.type === "media" && !artifact.timestamp && typeof artifact.data.exif_local_time === "string" && (
        <p className="rounded-md bg-amber-950/50 px-3 py-2 text-xs text-amber-200">
          Camera time {artifact.data.exif_local_time} has no time zone, so it is not placed on the UTC timeline.
        </p>
      )}
      {artifact.source_plugin === "sleuthkit" && artifact.data.kind === "file" && !artifact.data.recovered_file && (
        <button className="btn-primary" onClick={async () => navigate(`/jobs/${(await api.recover(artifact.id)).id}`)}>
          {artifact.data.deleted ? "Recover deleted file content" : "Extract file content"}
        </button>
      )}
      {typeof artifact.data.recovered_file === "string" && (
        <div className="rounded-md border border-ink-700 p-3 text-xs">
          <p className="mb-2 text-slate-300">{fmtBytes(Number(artifact.data.size ?? 0))} · SHA-256 <span className="font-mono">{String(artifact.data.sha256 ?? "")}</span></p>
          <a className="btn-primary" href={`/api/jobs/${artifact.job_id}/files/${artifact.data.recovered_file}`} download>Download recovered file</a>
          <p className="mt-2 text-slate-500">Downloads are hashed and recorded in the audit log.</p>
        </div>
      )}

      <section aria-labelledby="tags-h">
        <h3 id="tags-h" className="label">Tags <kbd className="ml-1 text-slate-500">t</kbd></h3>
        <div className="mb-2 flex flex-wrap gap-1.5">
          {caseTags.map((t) => {
            const on = tags.some((x) => x.id === t.id);
            return (
              <button key={t.id} onClick={() => toggle(t)} aria-pressed={on}
                className={`rounded px-2 py-0.5 text-xs ${on ? "text-ink-950" : "border border-ink-700 text-slate-300 hover:border-slate-500"}`}
                style={on ? { background: t.color } : undefined}>
                {t.name}
              </button>
            );
          })}
        </div>
        <form onSubmit={addTag} className="flex gap-2">
          <label htmlFor="new-tag" className="sr-only">New tag</label>
          <input id="new-tag" ref={tagRef} className="input" placeholder="Add tag…" value={newTag}
            onChange={(e) => setNewTag(e.target.value)} list="tag-names" />
          <datalist id="tag-names">{caseTags.map((t) => <option key={t.id} value={t.name} />)}</datalist>
        </form>
      </section>

      <section aria-labelledby="notes-h">
        <h3 id="notes-h" className="label">Notes <kbd className="ml-1 text-slate-500">n</kbd></h3>
        <ul className="mb-2 space-y-2">
          {notes.map((n) => (
            <li key={n.id} className="rounded border-l-2 border-mark bg-ink-950 px-3 py-2 text-sm">
              <p className="whitespace-pre-wrap">{n.body}</p>
              <p className="mt-1 text-[11px] text-slate-500">{n.author} · {fmtUtc(n.created_at)}</p>
            </li>
          ))}
        </ul>
        <form onSubmit={addNote} className="space-y-2">
          <label htmlFor="new-note" className="sr-only">New note</label>
          <textarea id="new-note" ref={noteRef} className="input" rows={2} placeholder="Add an examiner note…"
            value={note} onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) addNote(e); }} />
          <button className="btn-ghost" disabled={!note.trim()}>Save note <span className="text-slate-500">Ctrl+Enter</span></button>
        </form>
      </section>

      <section>
        <h3 className="label">Raw data</h3>
        <pre className="whitespace-pre-wrap break-all rounded bg-ink-950 p-3 font-mono text-xs text-slate-300">
          {JSON.stringify(artifact.data, null, 2)}
        </pre>
      </section>
    </div>
  );
}

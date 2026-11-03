import { fmtUtc, type Artifact } from "../../api";

export default function Gallery({ items, selectedId, onSelect }: {
  items: Artifact[]; selectedId?: string; onSelect: (a: Artifact) => void;
}) {
  const media = items.filter((a) => a.type === "media");
  if (!media.length) return <p className="p-6 text-sm text-slate-400">No media in this view. Run the Media plugin on a phone dump.</p>;
  return (
    <ul className="grid min-h-0 flex-1 auto-rows-min grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3 overflow-auto p-4" aria-label="Media gallery">
      {media.map((a) => {
        const thumb = a.data.thumb as string | null;
        return (
          <li key={a.id}>
            <button onClick={() => onSelect(a)}
              className={`group block w-full overflow-hidden rounded-lg border text-left ${selectedId === a.id ? "border-mark ring-2 ring-mark" : "border-ink-700 hover:border-slate-500"}`}>
              <div className="flex aspect-square items-center justify-center bg-ink-950">
                {thumb
                  ? <img src={`/api/jobs/${a.job_id}/thumbs/${thumb}`} alt={a.title} loading="lazy" className="h-full w-full object-cover" />
                  : <span className="text-xs uppercase tracking-wide text-slate-500">{String(a.data.kind ?? "file")}</span>}
              </div>
              <div className="p-2">
                <p className="truncate text-xs text-slate-200">{a.title}</p>
                <p className="truncate text-[10px] text-slate-500">
                  {a.timestamp ? fmtUtc(a.timestamp) : a.data.exif_local_time ? `${a.data.exif_local_time} (local, zone unknown)` : "no time"}
                  {a.data.Latitude !== undefined && " · GPS"}
                </p>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

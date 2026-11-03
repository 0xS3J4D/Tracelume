import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

type Device = { udid: string; DeviceName?: string; ProductType?: string; ProductVersion?: string };

/** iPhone logical backup over USB (Linux hosts). */
export default function AcquireIos({ caseId }: { caseId: string }) {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  useEffect(() => { api.acquireStatus().then((s) => setAvailable(s.usb_available)).catch(() => setAvailable(false)); }, []);

  const scan = async () => {
    setBusy(true); setError(null); setDevices(null);
    try {
      const job = await api.acquireIos(caseId, "list");
      for (let i = 0; i < 40; i++) {
        const j = await api.job(job.id);
        if (j.status === "succeeded") { setDevices(await api.acquireDevices(job.id)); break; }
        if (j.status === "failed") { setError(j.error ?? "scan failed"); break; }
        await new Promise((r) => setTimeout(r, 1000));
      }
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <details className="card mb-6 p-4">
      <summary className="cursor-pointer font-medium text-slate-100">Acquire an iPhone backup over USB <span className="ml-2 rounded bg-ink-700 px-1.5 py-0.5 text-xs text-slate-300">beta · Linux</span></summary>
      {available === false ? (
        <p className="mt-3 text-sm text-slate-400">
          USB acquisition needs Tracelume on a <b>Linux</b> computer (Docker Desktop on Windows and macOS cannot pass USB devices to containers).
          On Windows/macOS, make an unencrypted backup with Finder/iTunes or Apple Devices, zip the backup folder, and register it above as <i>iOS backup</i>.
        </p>
      ) : (
        <div className="mt-3 space-y-3 text-sm">
          <ol className="list-decimal space-y-1 pl-5 text-slate-400">
            <li>Connect the iPhone with a cable and unlock it.</li>
            <li>When asked, tap <b>Trust</b> and enter the passcode (only needed once per device).</li>
            <li>Choose the device below. The backup is hashed and registered as evidence automatically.</li>
          </ol>
          <p className="text-xs text-slate-400">Only for devices you are authorised to acquire. This is a standard logical backup; no security is bypassed.
            If “Encrypt local backup” is enabled on the phone, the backup will be encrypted.</p>
          <button className="btn-ghost" onClick={scan} disabled={busy}>{busy ? "Looking for devices…" : "Find connected iPhones"}</button>
          {error && <p role="alert" className="text-red-300">{error}</p>}
          {devices && !devices.length && <p className="text-slate-400">No device found. Check the cable, unlock the phone, and on the host run <code>sudo systemctl stop usbmuxd</code>.</p>}
          <ul className="space-y-2">
            {devices?.map((d) => (
              <li key={d.udid} className="flex items-center justify-between rounded-md border border-ink-700 p-3">
                <div>
                  <p className="text-slate-100">{d.DeviceName || "iPhone"} <span className="text-slate-400">{d.ProductType} · iOS {d.ProductVersion}</span></p>
                  <p className="font-mono text-xs text-slate-400">{d.udid}</p>
                </div>
                <button className="btn-primary" onClick={async () => {
                  try { navigate(`/jobs/${(await api.acquireIos(caseId, "backup", d.udid)).id}`); } catch (e) { setError((e as Error).message); }
                }}>Start backup</button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </details>
  );
}

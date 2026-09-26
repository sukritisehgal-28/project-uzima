import { useEffect, useMemo, useRef, useState } from "react";
import QRCode from "qrcode";
import MapView, { STATUS } from "./MapView";
import { WS, accept, getCenters, getStatus, startTransfer, type Card, type Twin } from "./api";

const CASES: { key: string; label: string; detail: string }[] = [
  { key: "cardiac_icu", label: "Heart attack", detail: "needs a cath lab and cardiac ICU" },
  { key: "stroke_thrombectomy", label: "Stroke", detail: "needs a thrombectomy team" },
  { key: "trauma_adult", label: "Trauma", detail: "needs a Level I or II trauma center" },
  { key: "trauma_burn", label: "Burn", detail: "needs a verified burn center" },
  { key: "trauma_pediatric", label: "Pediatric", detail: "needs a pediatric trauma center" },
];

export default function App() {
  const [specialty, setSpecialty] = useState("cardiac_icu");
  const [sending, setSending] = useState<{ lat: number; lng: number; name: string; short_name?: string }>();
  const [names, setNames] = useState<Record<string, string>>({});
  const [windows, setWindows] = useState<Record<string, any>>({});
  const [tid, setTid] = useState<string>();
  const [cards, setCards] = useState<Record<string, Card>>({});
  const [startedAt, setStartedAt] = useState<number>();
  const [stoppedAt, setStoppedAt] = useState<number>();
  const [now, setNow] = useState(Date.now());
  const [rec, setRec] = useState<any>();
  const [twin, setTwin] = useState<Twin>();
  const [qr, setQr] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const tidRef = useRef<string>();

  useEffect(() => {
    getCenters().then((d) => {
      setSending(d.sending);
      setNames(Object.fromEntries(d.centers.map((c: any) => [c.id, c.short_name ?? c.name])));
      setWindows(Object.fromEntries(Object.entries(d.demo_cases).map(([k, v]: [string, any]) => [k, d.windows[v.window]])));
    }).catch(() => setError("The orchestrator is not reachable on port 8000. Run make dev."));
  }, []);
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 250); return () => clearInterval(t); }, []);

  useEffect(() => {
    const ws = new WebSocket(WS);
    ws.onmessage = (m) => {
      const e = JSON.parse(m.data);
      if (e.transfer_id !== tidRef.current) return;
      if (e.kind === "result") setCards((c) => ({ ...c, [e.agent_id]: { ...c[e.agent_id], ...e, last_line: e.transcript?.at(-1)?.text } }));
      if (e.kind === "transfer") {
        const set = (hid: string, status: string) => setCards((c) => Object.fromEntries(Object.entries(c).map(([k, v]) => [k, v.hospital_id === hid ? { ...v, status } : v])));
        if (e.type === "held" || e.type === "accepted") set(e.hospital_id, e.type);
        if (e.type === "released") set(e.hospital_id, "released");
        if (e.type === "twin_ready") setTwin(e.data);
      }
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    if (!tid) return;
    const t = setInterval(async () => { try { setRec((await getStatus(tid)).recommendation); } catch { /* transient */ } }, 1000);
    return () => clearInterval(t);
  }, [tid]);

  useEffect(() => {
    if (!twin) return setQr(undefined);
    QRCode.toDataURL(twin.shlink, { margin: 1, width: 152, errorCorrectionLevel: "L", color: { dark: "#0B0D10", light: "#E6E8EB" } }).then(setQr);
  }, [twin]);

  async function onStart() {
    setError(undefined); setTwin(undefined); setRec(undefined); setStoppedAt(undefined);
    try {
      const r = await startTransfer(specialty);
      tidRef.current = r.transfer_id; setTid(r.transfer_id); setStartedAt(Date.now());
      setCards(Object.fromEntries(r.agents.map((a) => [a.agent_id, { ...a, status: "calling" }])));
    } catch { setError("Could not start the search. Is make dev running?"); }
  }
  async function onAccept() {
    if (!tid) return;
    setBusy(true);
    try { await accept(tid, rec?.hospital_id); setStoppedAt(Date.now()); } catch (e: any) { setError(String(e.message ?? e)); }
    setBusy(false);
  }

  const list = useMemo(() => Object.values(cards), [cards]);
  const n = list.length;
  const count = (...s: string[]) => list.filter((c) => s.includes(c.status)).length;
  const calling = count("calling", "callback_requested"), yes = count("available", "held", "accepted", "released"), no = count("declined"), none = count("no_answer");
  const searching = n > 0 && !twin && calling > 0;
  const elapsed = startedAt ? Math.floor(((stoppedAt ?? now) - startedAt) / 1000) : 0;
  const perCall = 90;
  const oneByOne = Math.min(Math.max(n, 1), 1 + Math.floor(elapsed / perCall));
  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const w = windows[specialty];
  const caseInfo = CASES.find((c) => c.key === specialty)!;
  const accepted = list.find((c) => c.status === "accepted");
  const released = count("released");

  return (
    <div className="grid h-full grid-cols-[minmax(0,1fr)] grid-rows-[auto_auto_1fr_auto] overflow-x-hidden">
      {/* Top bar */}
      <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-ink-line px-5 py-3">
        <div className="flex min-w-0 items-baseline gap-3">
          <span className="whitespace-nowrap text-[17px] font-semibold tracking-tight">Marco Polo</span>
          <span className="truncate text-sm text-ink-muted">{sending?.name ?? "…"}, Indianola, MS</span>
        </div>
        <div className="flex max-w-full flex-wrap items-center gap-2">
          <div className="flex max-w-full overflow-x-auto rounded-md border border-ink-line">
            {CASES.map((c, i) => (
              <button key={c.key} onClick={() => setSpecialty(c.key)} disabled={searching}
                className={`whitespace-nowrap px-3 py-1.5 text-sm ${i ? "border-l border-ink-line" : ""} ${specialty === c.key ? "bg-ink-raised text-ink-text" : "text-ink-muted hover:text-ink-text"} disabled:cursor-not-allowed`}>
                {c.label}
              </button>
            ))}
          </div>
          <button onClick={onStart} disabled={searching}
            className="whitespace-nowrap rounded-md bg-brand px-4 py-1.5 text-sm font-semibold text-ink-bg hover:bg-[#EB6A3C] disabled:opacity-50">
            {searching ? "Searching…" : twin ? "New search" : "Find a bed"}
          </button>
        </div>
      </header>

      {/* Status strip */}
      <section className="grid grid-cols-1 gap-px border-b border-ink-line bg-ink-line text-sm sm:grid-cols-2 xl:grid-cols-[1fr_1.2fr_1.7fr_1.4fr]">
        <div className="bg-ink-bg px-5 py-2.5">
          <div className="text-xs text-ink-muted">Elapsed · all at once</div>
          <div className={`text-xl font-semibold tabular ${twin ? "text-st-yes" : ""}`}>{fmt(elapsed)}{twin && <span className="ml-2 text-sm font-normal text-ink-muted">placed</span>}</div>
        </div>
        <div className="bg-ink-bg px-5 py-2.5">
          <div className="text-xs text-ink-muted">One at a time · ~{perCall} s per call</div>
          <div className="whitespace-nowrap text-xl font-semibold tabular text-ink-muted">{n ? <>call {oneByOne} of {n} <span className="text-sm font-normal">· {fmt(n * perCall)} total</span></> : "—"}</div>
        </div>
        <div className="bg-ink-bg px-5 py-2.5">
          <div className="text-xs text-ink-muted">Responses {n ? `(${n - calling} of ${n})` : ""}</div>
          <div className="flex flex-wrap gap-x-4 text-base font-medium tabular">
            <span className="text-st-yes">{yes} available</span><span className="text-st-no">{no} declined</span>
            <span className="text-ink-muted">{none} no answer</span><span className="text-st-calling">{calling} pending</span>
          </div>
        </div>
        <div className="bg-ink-bg px-5 py-2.5">
          <div className="truncate text-xs text-ink-muted">{caseInfo.label}: {caseInfo.detail}</div>
          <div className="text-base font-medium">{w ? <>Transport within {w.transport_budget_min} min <span className="text-ink-muted">(max {w.hard_max_min})</span></> : "—"}</div>
        </div>
      </section>

      {/* Map */}
      <section className="relative min-h-[380px]">
        <MapView sending={sending} cards={list} names={names} focusKey={tid} searching={searching} />
        <div className="pointer-events-none absolute left-3 top-3 rounded border border-ink-line bg-ink-panel px-3 py-2 text-xs">
          <div className="font-medium text-ink-text">Patient: 62-year-old man, {caseInfo.label.toLowerCase()}</div>
          <div className="text-ink-muted">{tid ? `Transfer ${tid}` : "No active transfer"}</div>
        </div>
      </section>

      {/* Decision bar */}
      <footer className="grid grid-cols-1 gap-px border-t border-ink-line bg-ink-line lg:grid-cols-5">
        <div className="bg-ink-bg px-5 py-3 lg:col-span-3">
          {error ? <div className="text-sm text-st-no">{error}</div>
            : accepted ? (
              <div>
                <div className="text-xs text-st-yes">Transfer accepted</div>
                <div className="text-base font-semibold">{accepted.hospital}</div>
                <div className="text-sm text-ink-muted">Physician-to-physician call started, case summary sent, {released} other {released === 1 ? "hospital" : "hospitals"} released.</div>
              </div>
            ) : rec ? (
              <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
                <div>
                  <div className="text-xs text-ink-muted">Recommended: earliest treatment</div>
                  <div className="text-base font-semibold">{rec.hospital}</div>
                  <div className="mt-0.5 flex gap-5 text-sm tabular text-ink-muted">
                    <span>Treatment in <b className="text-ink-text">~{rec.treatment_start_min} min</b></span>
                    <span>{rec.transport.recommended_mode === "air" ? "Air" : "Ground"} <b className="text-ink-text">{rec.transport.recommended_mode === "air" ? rec.transport.est_air_min : rec.transport.est_ground_min} min</b></span>
                    <span>Ready in <b className="text-ink-text">{rec.ready_in_min} min</b></span>
                  </div>
                </div>
                <div className="flex flex-col items-end">
                  <button onClick={onAccept} disabled={busy} className="rounded-md bg-st-yes px-4 py-2 text-sm font-semibold text-ink-bg hover:brightness-110 disabled:opacity-50">
                    {busy ? "Confirming…" : "Accept and release others"}
                  </button>
                  <span className="mt-1 text-xs text-ink-faint">Accepting physician confirms on the call</span>
                </div>
              </div>
            ) : (
              <div className="text-sm text-ink-muted">{n ? "Waiting for the first hospital to say yes…" : "Choose the condition and press Find a bed. Every hospital that can treat it within the time window is called at once."}</div>
            )}
        </div>
        <div className="bg-ink-bg px-5 py-3 lg:col-span-2">
          {twin ? (
            <div className="flex items-center gap-4">
              {qr && <img src={qr} alt="QR code for the handoff record" className="h-[76px] w-[76px] rounded-sm" />}
              <div className="min-w-0 text-sm">
                <div className="text-xs text-ink-muted">Handoff record sent to {twin.hospital}</div>
                <div>Passcode <span className="font-mono tracking-wider">{twin.passcode}</span> <span className="text-ink-faint">· expires in 24 h</span></div>
                <div className="truncate text-xs text-ink-faint">Insurance check: {twin.insurance?.payer}</div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-ink-muted">After acceptance, an encrypted handoff record (case, every call, insurance check) goes to the receiving team.</div>
          )}
        </div>
      </footer>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import MapView from "./MapView";
import { LABEL, WS, accept, getCenters, getStatus, startTransfer, type Card, type Twin } from "./api";

// Every status is a color + a word (colorblind-safe).
const STATUS: Record<string, { label: string; cls: string }> = {
  calling: { label: "Calling…", cls: "text-yellow-300" },
  available: { label: "Available", cls: "text-green-400" },
  declined: { label: "Declined", cls: "text-red-400" },
  no_answer: { label: "No answer", cls: "text-slate-400" },
  callback_requested: { label: "Call back in 5", cls: "text-yellow-200" },
  held: { label: "Held", cls: "text-green-300" },
  released: { label: "Released", cls: "text-slate-500" },
  accepted: { label: "Accepted", cls: "text-green-400 font-bold" },
};

export default function App() {
  const [specialty, setSpecialty] = useState("cardiac_icu");
  const [sending, setSending] = useState<{ lat: number; lng: number; name: string }>();
  const [tid, setTid] = useState<string>();
  const [cards, setCards] = useState<Record<string, Card>>({});
  const [startedAt, setStartedAt] = useState<number>();
  const [stoppedAt, setStoppedAt] = useState<number>();
  const [now, setNow] = useState(Date.now());
  const [rec, setRec] = useState<any>();
  const [twin, setTwin] = useState<Twin>();
  const [error, setError] = useState<string>();
  const tidRef = useRef<string>();

  useEffect(() => { getCenters().then((d) => setSending(d.sending)).catch(() => setError("Orchestrator not reachable on :8000 — run make dev")); }, []);
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
    const t = setInterval(async () => { const s = await getStatus(tid); setRec(s.recommendation); }, 1000);
    return () => clearInterval(t);
  }, [tid]);

  async function onStart() {
    setError(undefined); setTwin(undefined); setRec(undefined); setStoppedAt(undefined);
    const r = await startTransfer(specialty);
    tidRef.current = r.transfer_id; setTid(r.transfer_id); setStartedAt(Date.now());
    setCards(Object.fromEntries(r.agents.map((a) => [a.agent_id, { ...a, status: "calling" }])));
  }
  async function onAccept() {
    if (!tid) return;
    try { await accept(tid, rec?.hospital_id); setStoppedAt(Date.now()); } catch (e: any) { setError(String(e.message ?? e)); }
  }

  const elapsed = startedAt ? Math.floor(((stoppedAt ?? now) - startedAt) / 1000) : 0;
  const list = useMemo(() => Object.values(cards).sort((a, b) => (a.treatment_start_min ?? 9e9) - (b.treatment_start_min ?? 9e9) || a.agent_id.localeCompare(b.agent_id, undefined, { numeric: true })), [cards]);
  const oneByOne = Math.min(Math.max(list.length, 1), 1 + Math.floor(elapsed / 90));
  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="grid h-screen grid-cols-5 grid-rows-[auto_1fr_auto] gap-4 p-4">
      <header className="col-span-5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Marco Polo</h1>
          <span className="text-slate-400">{sending?.name ?? "…"}, Indianola MS</span>
          <select className="rounded bg-slate-800 px-2 py-1" value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
            {Object.entries(LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <button className="rounded bg-orange-500 px-4 py-1 font-semibold text-black" onClick={onStart}>Find a bed</button>
        </div>
        <div className="flex gap-6 font-mono text-xl">
          <span>Marco Polo {fmt(elapsed)}</span>
          <span className="text-slate-400">one by one: still on call {oneByOne} of {list.length || "–"}</span>
        </div>
      </header>
      <section className="col-span-3 row-span-1 overflow-hidden rounded-xl bg-slate-900"><MapView sending={sending} cards={list} /></section>
      <aside className="col-span-2 space-y-2 overflow-auto">
        {error && <div className="rounded bg-red-900/50 p-2 text-sm">{error}</div>}
        {list.map((c) => (
          <div key={c.agent_id} className="rounded-lg bg-slate-900 p-3">
            <div className="flex justify-between"><span className="font-mono">{c.agent_id}{c.live ? " · live" : ""}</span><span className={STATUS[c.status]?.cls}>{STATUS[c.status]?.label ?? c.status}{c.decline_reason ? ` · ${c.decline_reason}` : ""}</span></div>
            <div className="text-lg">{c.hospital}</div>
            <div className="text-sm text-slate-400">{c.transport.recommended_mode} · {c.transport.recommended_mode === "air" ? c.transport.est_air_min : c.transport.est_ground_min} min{c.ready_in_min != null ? ` · ready in ${c.ready_in_min}` : ""} · {c.transport.tier.replaceAll("_", " ")}</div>
            {c.last_line && <div className="text-sm italic text-slate-300">“{c.last_line}”</div>}
          </div>
        ))}
      </aside>
      <footer className="col-span-5 grid grid-cols-5 gap-4">
        <div className="col-span-3 rounded-lg bg-slate-900 p-3">
          {rec ? <>Recommended: <b>{rec.hospital}</b> · treatment in ~{rec.treatment_start_min} min · {rec.transport.recommended_mode}
            <button disabled={!!twin} className="ml-4 rounded bg-green-500 px-3 py-1 text-black disabled:opacity-40" onClick={onAccept}>Accept & release others</button></>
            : <span className="text-slate-400">Waiting for a yes…</span>}
        </div>
        <div className="col-span-2 rounded-lg bg-slate-900 p-3 text-sm">
          {twin ? <>Handoff twin for <b>{twin.hospital}</b> · passcode <span className="font-mono">{twin.passcode}</span>
            <div className="truncate font-mono text-xs text-slate-400">{twin.shlink}</div>
            <div className="text-xs text-slate-500">Insurance: {twin.insurance?.payer} ({twin.insurance?.source})</div></>
            : <span className="text-slate-500">Demo: hospital responses A2–An are simulated. A1 is the live call when Twilio is configured.</span>}
        </div>
      </footer>
    </div>
  );
}

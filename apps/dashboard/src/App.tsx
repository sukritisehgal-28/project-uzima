import { useEffect, useState } from "react";

// Status colors always pair with a word and an icon (colorblind-safe).
const STATUS: Record<string, { label: string; cls: string }> = {
  calling: { label: "Calling…", cls: "text-yellow-300" },
  available: { label: "Available", cls: "text-green-400" },
  declined: { label: "Declined", cls: "text-red-400" },
  no_answer: { label: "No answer, retrying", cls: "text-slate-400" },
  callback_requested: { label: "Call back in 5", cls: "text-yellow-200" },
  held: { label: "Held", cls: "text-green-300" },
  released: { label: "Released", cls: "text-slate-500" },
  accepted: { label: "Accepted", cls: "text-green-400 font-bold" },
};

type Card = { agent_id: string; hospital: string; status: string; ready_in_min?: number; treatment_start_min?: number;
  transport?: { recommended_mode: string; est_ground_min: number; est_air_min: number; tier: string }; last_line?: string };

export default function App() {
  const [cards, setCards] = useState<Record<string, Card>>({});
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const ws = new WebSocket((import.meta as any).env.VITE_COLLECTOR_WS ?? "ws://localhost:8003/stream");
    ws.onmessage = (m) => {
      const e = JSON.parse(m.data);
      setCards((c) => {
        const prev = c[e.agent_id] ?? { agent_id: e.agent_id, hospital: e.hospital ?? e.hospital_id, status: "calling" };
        if (e.kind === "event") return { ...c, [e.agent_id]: { ...prev, status: e.type === "call_ended" ? (e.data.outcome ?? prev.status) : prev.status } };
        return { ...c, [e.agent_id]: { ...prev, ...e, last_line: e.transcript?.at(-1)?.text } };
      });
    };
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => { ws.close(); clearInterval(t); };
  }, []);
  const list = Object.values(cards).sort((a, b) => (a.treatment_start_min ?? 9e9) - (b.treatment_start_min ?? 9e9));
  const best = list.find((c) => c.status === "available");
  return (
    <div className="grid grid-cols-5 gap-4 p-4 h-screen">
      <header className="col-span-5 flex justify-between items-baseline">
        <h1 className="text-2xl font-semibold">Marco Polo · Indianola, MS → ICU search</h1>
        <div className="font-mono text-xl">swarm {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")} · one by one: still on call {Math.min(10, 1 + Math.floor(elapsed / 90))} of 10</div>
      </header>
      <section className="col-span-3 rounded-xl bg-slate-900" id="map">{/* MapLibre map with AWS Location tiles: sending hospital, lines pulse while calling */}</section>
      <aside className="col-span-2 space-y-2 overflow-auto">
        {list.map((c) => (
          <div key={c.agent_id} className="rounded-lg bg-slate-900 p-3">
            <div className="flex justify-between"><span className="font-mono">{c.agent_id}</span><span className={STATUS[c.status]?.cls}>{STATUS[c.status]?.label ?? c.status}</span></div>
            <div className="text-lg">{c.hospital}</div>
            <div className="text-sm text-slate-400">{c.transport?.recommended_mode} · {c.transport?.recommended_mode === "air" ? c.transport?.est_air_min : c.transport?.est_ground_min} min · {c.ready_in_min != null ? `ready in ${c.ready_in_min}` : ""} · {c.transport?.tier}</div>
            {c.last_line && <div className="text-sm italic text-slate-300">“{c.last_line}”</div>}
          </div>
        ))}
        {best && <div className="rounded-lg bg-green-900/40 p-3">Recommended: <b>{best.hospital}</b> · treatment in ~{best.treatment_start_min} min
          <div className="mt-2 flex gap-2"><button className="rounded bg-green-500 px-3 py-1 text-black">Accept & release others</button><button className="rounded bg-slate-700 px-3 py-1">Choose another</button></div></div>}
        <div className="text-xs text-slate-500">Demo: hospital responses A2–A10 are simulated. A1 is a live call to a teammate.</div>
      </aside>
    </div>
  );
}

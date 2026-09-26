import { useEffect, useMemo, useRef, useState } from "react";
import QRCode from "qrcode";
import MapView from "./MapView";
import { WS, accept, getCenters, getHealth, getStatus, startTransfer, type Card, type Ticket, type Twin } from "./api";

const CASES: { key: string; label: string; detail: string }[] = [
  { key: "cardiac_icu", label: "Heart attack", detail: "needs a cath lab and cardiac ICU" },
  { key: "stroke_thrombectomy", label: "Stroke", detail: "needs a thrombectomy team" },
  { key: "trauma_adult", label: "Trauma", detail: "needs a Level I or II trauma center" },
  { key: "trauma_burn", label: "Burn", detail: "needs a verified burn center" },
  { key: "trauma_pediatric", label: "Pediatric", detail: "needs a pediatric trauma center" },
];

/** "2026-09-26T18:22:00Z" -> "1:22 PM" in the viewer's time zone. */
function clock(iso?: string): string {
  const d = iso ? new Date(iso) : undefined;
  return d && !Number.isNaN(d.getTime()) ? d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) : "—";
}
/** "482913" -> "482 913", easier to read aloud. */
const spaced = (code: string | number) => String(code).replace(/(\d{3})(?=\d)/g, "$1 ");

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
  const [windowMin, setWindowMin] = useState<number>();
  const [error, setError] = useState<string>();
  const [liveCalls, setLiveCalls] = useState(false);   // real phone calls only when the Twilio gateway is live
  const tidRef = useRef<string>();

  useEffect(() => {
    getCenters().then((d) => {
      setSending(d.sending);
      setNames(Object.fromEntries(d.centers.map((c: any) => [c.id, c.short_name ?? c.name])));
      setWindows(Object.fromEntries(Object.entries(d.demo_cases).map(([k, v]: [string, any]) => [k, d.windows[v.window]])));
    }).catch(() => setError("The orchestrator is not reachable on port 8000. Run make dev."));
    getHealth().then((h) => setLiveCalls(h?.integrations?.twilio === "live")).catch(() => {});
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

  // The QR opens the transfer ticket on a phone; older backends without a ticket get the handoff record link instead.
  useEffect(() => {
    if (!twin) return setQr(undefined);
    let live = true;
    const text = twin.ticket?.url ?? twin.shlink;
    QRCode.toDataURL(text, { margin: 1, width: 224, errorCorrectionLevel: twin.ticket ? "M" : "L", color: { dark: "#0A0B0D", light: "#FFFFFF" } })
      .then((u) => { if (live) setQr(u); }).catch(() => { if (live) setQr(undefined); });
    return () => { live = false; };
  }, [twin]);

  async function onStart() {
    setError(undefined); setTwin(undefined); setRec(undefined); setStoppedAt(undefined);
    try {
      const r = await startTransfer(specialty, windowMin);   // untouched slider = the case default window
      tidRef.current = r.transfer_id; setTid(r.transfer_id); setStartedAt(Date.now());
      setCards(Object.fromEntries(r.agents.map((a) => [a.agent_id, { ...a, live: a.live && liveCalls, status: "calling" }])));   // no LIVE tag in a simulated run
    } catch { setError("Could not start the search. Is make dev running?"); }
  }
  async function onAccept() {
    if (!tid) return;
    setBusy(true);
    try {
      const r = await accept(tid, rec?.hospital_id);
      setStoppedAt(Date.now());
      if (r?.twin && tidRef.current === tid) setTwin(r.twin);   // same twin as the websocket twin_ready event, in case that is missed
    } catch (e: any) { setError(String(e.message ?? e)); }
    setBusy(false);
  }

  const list = useMemo(() => Object.values(cards), [cards]);
  const n = list.length;
  const count = (...s: string[]) => list.filter((c) => s.includes(c.status)).length;
  const calling = count("calling"), callback = count("callback_requested"), yes = count("available", "held", "accepted", "released"), no = count("declined"), none = count("no_answer");
  const searching = n > 0 && !twin && calling > 0;
  const elapsed = startedAt ? Math.floor(((stoppedAt ?? now) - startedAt) / 1000) : 0;
  const perCall = 90;
  const oneByOne = Math.min(Math.max(n, 1), 1 + Math.floor(elapsed / perCall));
  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const w0 = windows[specialty];
  const w = w0 && windowMin ? { ...w0, transport_budget_min: windowMin, hard_max_min: windowMin } : w0;
  const caseInfo = CASES.find((c) => c.key === specialty)!;
  const accepted = list.find((c) => c.status === "accepted");
  const acceptedName = accepted?.hospital ?? twin?.hospital;   // a twin only exists once a hospital accepted
  const released = count("released");
  const ticket = twin?.ticket;

  return (
    <div className="grid min-h-full grid-cols-[minmax(0,1fr)] grid-rows-[auto_auto_minmax(340px,1fr)_auto] overflow-x-hidden">
      {/* Top bar */}
      <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-ink-line px-5 py-3">
        <div className="flex min-w-0 items-baseline gap-3">
          <span className="whitespace-nowrap text-[18px] font-semibold tracking-[-0.025em]">Project Uzima</span>
          <span className="truncate text-sm text-ink-muted">{sending?.name ?? "…"}, Indianola, MS</span>
        </div>
        <div className="flex max-w-full flex-wrap items-center gap-2.5">
          <div className="flex max-w-full overflow-x-auto rounded-full border border-ink-line bg-ink-panel p-0.5">
            {CASES.map((c) => (
              <button key={c.key} onClick={() => { setSpecialty(c.key); setWindowMin(undefined); }} disabled={searching}
                className={`whitespace-nowrap rounded-full px-3 py-1 text-sm transition-colors ${specialty === c.key ? "bg-ink-raised font-medium text-ink-text" : "text-ink-muted enabled:hover:text-ink-text"} disabled:cursor-not-allowed`}>
                {c.label}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 whitespace-nowrap text-sm text-ink-muted">
            Care within
            <input type="range" min={10} max={120} step={5} disabled={searching}
              value={windowMin ?? windows[specialty]?.transport_budget_min ?? 60}
              onChange={(e) => setWindowMin(Number(e.target.value))} className="w-28 accent-[#F0C06A]" />
            <b className="tabular font-medium text-ink-text">{windowMin ?? windows[specialty]?.transport_budget_min ?? 60} min</b>
          </label>
          <button onClick={onStart} disabled={searching} className="btn-primary">
            {searching ? "Searching…" : twin ? "New search" : "Find a bed"}
          </button>
        </div>
      </header>

      {/* Status strip */}
      <section className="grid grid-cols-1 gap-px border-b border-ink-line bg-ink-line text-sm sm:grid-cols-2 xl:grid-cols-[1fr_1.2fr_1.7fr_1.4fr]">
        <div className="bg-ink-bg px-5 py-2.5">
          <div className="eyebrow">Elapsed · all at once</div>
          <div className={`mt-0.5 text-xl font-semibold tabular ${twin ? "text-st-yes" : ""}`}>
            {fmt(elapsed)}{twin && <span className="ml-2 font-serif text-[19px] font-normal italic">placed</span>}
          </div>
        </div>
        <div className="bg-ink-bg px-5 py-2.5">
          <div className="eyebrow">One at a time · ~{perCall} sec per call</div>
          <div className="mt-0.5 whitespace-nowrap text-xl font-semibold tabular text-ink-muted">{n ? <>call {oneByOne} of {n} <span className="text-sm font-normal">· {fmt(n * perCall)} total</span></> : "—"}</div>
        </div>
        <div className="bg-ink-bg px-5 py-2.5">
          <div className="eyebrow">Responses {n ? `(${n - calling} of ${n})` : ""}</div>
          <div className="mt-1 flex flex-wrap gap-x-4 text-base font-medium tabular">
            <Count dot="bg-fill-yes" className="text-st-yes">{yes} available</Count>
            <Count dot="bg-fill-no" className="text-st-no">{no} declined</Count>
            <Count dot="bg-fill-none" className="text-st-none">{none} no answer</Count>
            {callback > 0 && <Count dot="bg-fill-calling" className="text-st-calling">{callback} call back</Count>}
            <Count dot="bg-fill-calling" className="text-st-calling">{calling} pending</Count>
          </div>
        </div>
        <div className="min-w-0 bg-ink-bg px-5 py-2.5">
          <div className="flex min-w-0 items-baseline gap-2" title={`${caseInfo.label}: ${caseInfo.detail}`}>
            <span className="eyebrow shrink-0">{caseInfo.label}</span>
            <span className="truncate text-xs text-ink-muted">{caseInfo.detail}</span>
          </div>
          <div className="mt-0.5 text-base font-medium">{w ? <>Transport within {w.transport_budget_min} min <span className="font-normal text-ink-muted">(max {w.hard_max_min})</span></> : "—"}</div>
        </div>
      </section>

      {/* Map */}
      <section className="relative min-h-[380px]">
        <MapView sending={sending} cards={list} names={names} focusKey={tid} searching={searching} />
        <div className="pointer-events-none absolute left-3 top-3 rounded-lg border border-ink-line bg-ink-panel px-3 py-2 text-xs shadow-xs">
          <div className="font-medium text-ink-text">Patient: 62-year-old man, {caseInfo.label.toLowerCase()}</div>
          <div className="mt-0.5 text-ink-muted">{tid ? <>Transfer <span className="font-mono text-[11px]">{tid}</span></> : "No active transfer"}</div>
        </div>
      </section>

      {/* Decision bar. With a ticket, the ticket gets the wider column. */}
      <footer className={`grid grid-cols-1 gap-px border-t border-ink-line bg-ink-line ${ticket
        ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]" : "lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]"}`}>
        <div className="bg-ink-bg px-5 py-3">
          {error ? <div className="text-sm text-st-no">{error}</div>
            : acceptedName ? (
              <div>
                <div className="eyebrow flex items-center gap-1.5 text-st-yes"><span className="h-1.5 w-1.5 rounded-full bg-fill-yes" />Transfer accepted</div>
                <div className="mt-0.5 text-base font-semibold">{acceptedName}</div>
                <div className="text-sm text-ink-muted">
                  {liveCalls ? "Summary read to the hospital on the call, doctors connected" : "Simulated run, no phones dialed"}{ticket ? ", transfer ticket created" : ""}
                  {released ? `, ${released} other ${released === 1 ? "hospital" : "hospitals"} released` : ""}.
                </div>
                {ticket && twin && (
                  <div className="mt-3 max-w-md rounded-lg border border-ink-line bg-ink-panel px-3 py-2 shadow-xs">
                    <div className="eyebrow">Record passcode</div>
                    <div className="flex flex-wrap items-baseline gap-x-3">
                      <span className="font-mono text-lg font-medium tracking-[.14em] text-ink-text">{spaced(twin.passcode)}</span>
                      <span className="text-xs text-ink-muted">read to the receiving team on the call</span>
                    </div>
                  </div>
                )}
              </div>
            ) : rec ? (
              <div className="win flex flex-wrap items-center justify-between gap-x-6 gap-y-3 rounded-xl px-4 py-3">
                <div className="min-w-0">
                  <div className="eyebrow text-gold-text">Recommended · earliest treatment</div>
                  <div className="mt-0.5 text-base font-semibold">{rec.hospital}</div>
                  <div className="mt-0.5 flex flex-wrap gap-x-5 text-sm tabular text-ink-muted">
                    <span>Treatment in <b className="font-semibold text-ink-text">~{rec.treatment_start_min} min</b></span>
                    <span>{rec.transport.recommended_mode === "air" ? "Air" : "Ground"} <b className="font-semibold text-ink-text">{rec.transport.recommended_mode === "air" ? rec.transport.est_air_min : rec.transport.est_ground_min} min</b></span>
                    <span>Ready in <b className="font-semibold text-ink-text">{rec.ready_in_min} min</b></span>
                  </div>
                </div>
                <div className="flex flex-col items-start sm:items-end">
                  <button onClick={onAccept} disabled={busy} className="btn-primary">
                    {busy ? "Connecting…" : "Connect doctors"}
                  </button>
                  <span className="mt-1 text-xs text-ink-muted">The agent reads the summary to them, then you are connected</span>
                </div>
              </div>
            ) : (
              <div className="text-sm text-ink-muted">{n ? "Waiting for the first hospital to say yes…" : "Choose the condition and press Find a bed. Every hospital that can treat it within the time window is called at once."}</div>
            )}
        </div>
        <div className="bg-ink-bg px-5 py-3">
          {ticket ? <TicketCard t={ticket} qr={qr} />
            : twin ? (
              <div className="flex items-center gap-4">
                {qr && <img src={qr} alt="QR code for the handoff record" className="h-[76px] w-[76px] rounded-sm" />}
                <div className="min-w-0 text-sm">
                  <div className="text-xs text-ink-muted">Handoff record sent to {twin.hospital}</div>
                  <div>Passcode <span className="font-mono tracking-wider">{twin.passcode}</span> <span className="text-ink-faint">· expires in 24 h</span></div>
                  <div className="truncate text-xs text-ink-faint">Insurance check: {twin.insurance?.payer}</div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-ink-muted">After Connect, the agent reads the summary on the call and a transfer ticket is created for the patient. An encrypted record (case, every call, insurance check) is kept for the receiving team.</div>
            )}
        </div>
      </footer>
    </div>
  );
}

function Count({ dot, className, children }: { dot: string; className: string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap ${className}`}>
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${dot}`} />{children}
    </span>
  );
}

function Field({ k, v, sub }: { k: string; v: string; sub?: string }) {
  return (
    <div className="min-w-0">
      <dt className="eyebrow">{k}</dt>
      <dd className="truncate text-[13px] font-medium leading-5 text-ink-text" title={v}>{v}</dd>
      {sub && <dd className="truncate text-xs leading-4 text-ink-muted" title={sub}>{sub}</dd>}
    </div>
  );
}

/** The transfer ticket, laid out like a boarding pass: route and details on the left, a perforated stub with the QR on the right.
 *  The passcode is never on the ticket; the clinician sees it in the decision column. */
function TicketCard({ t, qr }: { t: Ticket; qr?: string }) {
  const mode = t.mode === "air" ? "Air" : "Ground";
  const insurance = t.insurance || "—";
  const cut = insurance.search(/ \(| · /);   // "Mississippi Medicaid (offline mock) · active" -> payer, then the rest underneath
  const city = "truncate text-base font-semibold leading-6 tracking-[-0.01em] sm:text-lg sm:leading-7 xl:text-[22px]";
  return (
    <article aria-label={`Transfer ticket ${t.code}`} className="flex flex-col overflow-hidden rounded-xl border border-ink-line bg-ink-panel shadow-xs sm:flex-row">
      <div className="min-w-0 flex-1 px-4 pb-3 pt-2.5">
        <div className="flex items-center justify-between gap-3">
          <span className="eyebrow flex items-center gap-1.5 text-gold-text"><span aria-hidden className="h-1.5 w-1.5 rounded-full bg-gold" />Ticket created</span>
          <span className="font-mono text-[13px] font-medium tracking-[.06em] text-ink-text">{t.code}</span>
        </div>

        <div className="mt-1.5 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-x-3">
          <div className={city} title={t.from?.city}>{t.from?.city}</div>
          <div aria-hidden className="flex h-[9px] w-10 items-center text-ink-faint sm:w-16 xl:w-24">
            <span className="h-[5px] w-[5px] shrink-0 rounded-full border border-current" />
            <span className="h-px flex-1 bg-current" />
            <svg viewBox="0 0 6 9" className="h-[9px] w-[6px] shrink-0"><path d="M0 4.5h5.4M2.2 1.5l3.2 3-3.2 3" fill="none" stroke="currentColor" strokeWidth="1" /></svg>
          </div>
          <div className={`${city} text-right`} title={t.to?.city}>{t.to?.city}</div>
          <div className="truncate text-xs text-ink-muted" title={t.from?.name}>{t.from?.name}</div>
          <div />
          <div className="truncate text-right text-xs text-ink-muted" title={t.to?.name}>{t.to?.name}</div>
        </div>

        <dl className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-2 border-t border-ink-line pt-2 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.3fr)]">
          <Field k="Patient" v={t.patient} sub={t.condition} />
          <Field k="Arrives" v={clock(t.eta)} sub={`${mode} · ${t.travel_min} min`} />
          <Field k="Team ready" v={t.ready_in_min != null ? `in ${t.ready_in_min} min` : "—"}
            sub={t.treatment_in_min != null ? `treatment ~${t.treatment_in_min} min` : undefined} />
          <Field k="Insurance" v={cut > 0 ? insurance.slice(0, cut) : insurance} sub={cut > 0 ? insurance.slice(cut + 1) : undefined} />
        </dl>

        <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-2">
          <a href={t.url} target="_blank" rel="noreferrer" className="btn-primary px-3.5 py-1 text-[13px]">Open ticket</a>
          {t.wallet_url
            ? <a href={t.wallet_url} target="_blank" rel="noreferrer" className="btn-secondary px-3.5 py-1 text-[13px]">Add to Apple Wallet</a>
            : <span className="min-w-[12rem] flex-1 text-[11px] leading-4 text-ink-muted">Apple Wallet needs a signing certificate; the web ticket works on any phone.</span>}
        </div>
      </div>

      <div className="flex items-center gap-3 border-t border-dashed border-ink-line px-4 py-3 sm:w-[136px] sm:shrink-0 sm:flex-col sm:justify-center sm:gap-2 sm:border-l sm:border-t-0">
        {qr ? <img src={qr} alt={`QR code that opens ticket ${t.code}`} className="h-[104px] w-[104px] shrink-0" />
          : <div className="h-[104px] w-[104px] shrink-0 rounded bg-ink-raised" />}
        <div className="text-[11px] leading-4 text-ink-muted sm:text-center">Scan to open the ticket on a phone</div>
      </div>
    </article>
  );
}

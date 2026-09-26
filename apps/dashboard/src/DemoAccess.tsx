import { useState, type ReactNode, type FormEvent } from "react";
import { ORCH } from "./api";

export default function DemoAccess({ children }: { children: ReactNode }) {
  const required = import.meta.env.VITE_REQUIRE_DEMO_ACCESS === "1";
  const [ready, setReady] = useState(!required || !!sessionStorage.getItem("uzima-demo-access"));
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function unlock(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await fetch(`${ORCH}/health`, { headers: { Authorization: `Bearer ${code.trim()}` } });
      if (!result.ok) throw new Error(result.status === 401 ? "That access code is not correct." : "The demo backend is unavailable. Ask the presenter to keep the host laptop running.");
      sessionStorage.setItem("uzima-demo-access", code.trim()); setReady(true);
    } catch (error) { setError(error instanceof Error ? error.message : "Could not connect to the demo."); }
    finally { setBusy(false); }
  }
  if (ready) return <>{children}</>;
  return <main className="flex min-h-screen items-center justify-center bg-ink-bg p-6">
    <form onSubmit={unlock} className="w-full max-w-sm rounded-2xl border border-ink-line bg-ink-panel p-7 shadow-xs">
      <p className="eyebrow text-gold-text">Project Uzima</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Open the live demo</h1>
      <p className="mt-2 text-sm leading-relaxed text-ink-muted">Enter the access code from the presenter. This dashboard can place calls to the configured demo phones.</p>
      <label htmlFor="access-code" className="mt-6 block text-sm font-medium">Demo access code</label>
      <input id="access-code" type="password" autoComplete="current-password" required value={code} onChange={(event) => setCode(event.target.value)}
        className="mt-2 w-full rounded-lg border border-ink-line bg-ink-bg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-gold" />
      {error && <p role="alert" className="mt-3 text-sm text-st-no">{error}</p>}
      <button type="submit" disabled={busy} className="btn-primary mt-4 w-full">{busy ? "Checking…" : "Open dashboard"}</button>
    </form>
  </main>;
}

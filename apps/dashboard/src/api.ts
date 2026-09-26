export const ORCH = import.meta.env.VITE_ORCHESTRATOR_URL ?? "http://localhost:8000";
export const WS = import.meta.env.VITE_COLLECTOR_WS ?? "ws://localhost:8003/stream";
// CARTO Dark Matter (free, no key): state borders and city names. Set VITE_MAP_STYLE to the AWS Location style URL when USE_AWS=1.
export const MAP_STYLE = import.meta.env.VITE_MAP_STYLE ?? "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export type Transport = { est_ground_min: number; est_air_min: number; recommended_mode: "ground" | "air"; tier: string };
export type Agent = { agent_id: string; hospital_id: string; hospital: string; lat: number; lng: number; live: boolean; transport: Transport };
export type Card = Agent & { status: string; ready_in_min?: number | null; decline_reason?: string | null; treatment_start_min?: number | null; last_line?: string };
export type Twin = { shlink: string; passcode: string; hospital: string; insurance?: { payer: string; source: string } };

export async function getCenters() {
  return (await fetch(`${ORCH}/centers`)).json();
}
export async function startTransfer(specialty: string) {
  const body = { age: 62, sex: "Male", specialty, condition: LABEL[specialty], onset_or_last_known_well: new Date().toISOString(), key_scores: {} };
  const r = await fetch(`${ORCH}/transfers`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return r.json() as Promise<{ transfer_id: string; agents: Agent[] }>;
}
export async function getStatus(tid: string) {
  return (await fetch(`${ORCH}/transfers/${tid}`)).json();
}
export async function accept(tid: string, hospital_id?: string) {
  const r = await fetch(`${ORCH}/transfers/${tid}/accept`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hospital_id, accepting_physician: "Dr. Accepting (demo)" }) });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
export const LABEL: Record<string, string> = {
  cardiac_icu: "Heart attack (STEMI)", stroke_thrombectomy: "Stroke, large-vessel", trauma_adult: "Severe trauma",
  trauma_burn: "Burn", trauma_pediatric: "Pediatric trauma",
};

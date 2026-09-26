// Same-origin relay for the public demo dashboard.
export default async function handler(request, response) {
  response.setHeader("Cache-Control", "no-store");
  const path = new URL(request.url, "https://dashboard.invalid").pathname.replace(/^\/api\//, "");
  const allowed = (request.method === "GET" && /^(health|centers|transfers\/[a-f0-9]{10})$/.test(path))
    || (request.method === "POST" && /^(transfers|transfers\/[a-f0-9]{10}\/accept)$/.test(path));
  if (!allowed) return response.status(404).json({ detail: "Unknown dashboard endpoint." });
  const origin = process.env.UZIMA_BACKEND_URL;
  if (!origin) return response.status(503).json({ detail: "The demo backend is not configured." });
  try {
    const result = await fetch(`${origin.replace(/\/$/, "")}/dashboard/${path}`, {
      method: request.method,
      headers: { "Content-Type": "application/json" },
      body: request.method === "POST" ? JSON.stringify(request.body) : undefined,
      signal: AbortSignal.timeout(50000),
      redirect: "error",
    });
    response.setHeader("Content-Type", "application/json");
    return response.status(result.status).send(await result.text());
  } catch {
    return response.status(503).json({ detail: "The demo backend is offline. Keep the host laptop and tunnel running." });
  }
}

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MAP_STYLE, type Card } from "./api";

const COLOR: Record<string, string> = {
  calling: "#facc15", available: "#22c55e", declined: "#ef4444", no_answer: "#94a3b8",
  callback_requested: "#fde68a", held: "#16a34a", accepted: "#16a34a", released: "#64748b",
};

export default function MapView({ sending, cards }: { sending?: { lat: number; lng: number; name: string }; cards: Card[] }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);

  useEffect(() => {
    if (!el.current || map.current) return;
    map.current = new maplibregl.Map({ container: el.current, style: MAP_STYLE, center: [-90.3, 33.4], zoom: 5.6 });
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m || !sending) return;
    const draw = () => {
      markers.current.forEach((x) => x.remove());
      markers.current = [new maplibregl.Marker({ color: "#e0592a" }).setLngLat([sending.lng, sending.lat]).setPopup(new maplibregl.Popup().setText(sending.name)).addTo(m)];
      const lines = cards.map((c) => ({ type: "Feature" as const, properties: { color: COLOR[c.status] ?? "#94a3b8", dash: c.status === "calling" ? 1 : 0 },
        geometry: { type: "LineString" as const, coordinates: [[sending.lng, sending.lat], [c.lng, c.lat]] } }));
      const data = { type: "FeatureCollection" as const, features: lines };
      const src = m.getSource("links") as maplibregl.GeoJSONSource | undefined;
      if (src) src.setData(data);
      else {
        m.addSource("links", { type: "geojson", data });
        m.addLayer({ id: "links", type: "line", source: "links", paint: { "line-color": ["get", "color"], "line-width": 3 } });
      }
      cards.forEach((c) => markers.current.push(new maplibregl.Marker({ color: COLOR[c.status] ?? "#94a3b8" })
        .setLngLat([c.lng, c.lat]).setPopup(new maplibregl.Popup().setText(`${c.agent_id} · ${c.hospital} · ${c.status}`)).addTo(m)));
    };
    m.loaded() ? draw() : m.once("load", draw);
  }, [sending, cards]);

  return <div ref={el} className="h-full w-full rounded-xl" />;
}

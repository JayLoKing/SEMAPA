import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import { useEffect, useState, useRef, useCallback } from "react";
import L from "leaflet";
import "leaflet.markercluster";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type FilterType = "all" | "activos" | "anomalias" | "morosos";

interface ZoneStats {
  zona: string;
  distrito: string;
  medidores_ref: number;
  consumo: number;
}

interface GatewayPoint {
  lat: number;
  lon: number;
  mac: string;
  estado: string;
  ultima_lectura?: string;
}

// ---------------------------------------------------------------------------
// GeoJSON data – approximate Cochabamba service zones
// ---------------------------------------------------------------------------
const ZONAS_CBB: any = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { zona: "Zona Central", distrito: "D1", medidores_ref: 12000 },
      geometry: {
        type: "Polygon",
        coordinates: [[[-66.165, -17.405], [-66.145, -17.405], [-66.145, -17.385], [-66.165, -17.385], [-66.165, -17.405]]],
      },
    },
    {
      type: "Feature",
      properties: { zona: "Zona Norte", distrito: "D2", medidores_ref: 18000 },
      geometry: {
        type: "Polygon",
        coordinates: [[[-66.175, -17.385], [-66.145, -17.385], [-66.145, -17.360], [-66.175, -17.360], [-66.175, -17.385]]],
      },
    },
    {
      type: "Feature",
      properties: { zona: "Zona Sur", distrito: "D3", medidores_ref: 15000 },
      geometry: {
        type: "Polygon",
        coordinates: [[[-66.165, -17.430], [-66.140, -17.430], [-66.140, -17.405], [-66.165, -17.405], [-66.165, -17.430]]],
      },
    },
    {
      type: "Feature",
      properties: { zona: "Zona Este (Sacaba)", distrito: "D4", medidores_ref: 14000 },
      geometry: {
        type: "Polygon",
        coordinates: [[[-66.140, -17.410], [-66.110, -17.410], [-66.110, -17.380], [-66.140, -17.380], [-66.140, -17.410]]],
      },
    },
    {
      type: "Feature",
      properties: { zona: "Zona Oeste (Quillacollo)", distrito: "D5", medidores_ref: 20000 },
      geometry: {
        type: "Polygon",
        coordinates: [[[-66.200, -17.400], [-66.165, -17.400], [-66.165, -17.375], [-66.200, -17.375], [-66.200, -17.400]]],
      },
    },
    {
      type: "Feature",
      properties: { zona: "Zona Sureste", distrito: "D6", medidores_ref: 11000 },
      geometry: {
        type: "Polygon",
        coordinates: [[[-66.140, -17.430], [-66.110, -17.430], [-66.110, -17.410], [-66.140, -17.410], [-66.140, -17.430]]],
      },
    },
    {
      type: "Feature",
      properties: { zona: "Valle Hermoso", distrito: "D7", medidores_ref: 9000 },
      geometry: {
        type: "Polygon",
        coordinates: [[[-66.200, -17.375], [-66.165, -17.375], [-66.165, -17.350], [-66.200, -17.350], [-66.200, -17.375]]],
      },
    },
    {
      type: "Feature",
      properties: { zona: "Colcapirhua", distrito: "D8", medidores_ref: 8000 },
      geometry: {
        type: "Polygon",
        coordinates: [[[-66.230, -17.400], [-66.200, -17.400], [-66.200, -17.370], [-66.230, -17.370], [-66.230, -17.400]]],
      },
    },
  ],
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const CENTRO: [number, number] = [-17.393, -66.157];

/** Deterministic pseudo-random based on zone name */
function seedRandom(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  }
  return Math.abs(h) / 2147483647;
}

function consumptionForZone(zona: string, apiData: any[]): number {
  if (apiData && apiData.length > 0) {
    const match = apiData.find(
      (d: any) =>
        d.zona?.toLowerCase().includes(zona.split(" ")[1]?.toLowerCase() ?? "") ||
        d.distrito?.toLowerCase() === zona.toLowerCase()
    );
    if (match?.consumo_total) return Number(match.consumo_total);
  }
  // Mock: seeded random between 800 and 35000
  const r = seedRandom(zona);
  return Math.round(800 + r * 34200);
}

function colorForConsumption(consumo: number): string {
  if (consumo < 1000) return "#93c5fd";
  if (consumo < 5000) return "#3b82f6";
  if (consumo < 15000) return "#1d4ed8";
  if (consumo < 30000) return "#1e3a8a";
  return "#0f172a";
}

function labelForConsumption(consumo: number): string {
  if (consumo < 1000) return "< 1 000 m³";
  if (consumo < 5000) return "1 000–5 000 m³";
  if (consumo < 15000) return "5 000–15 000 m³";
  if (consumo < 30000) return "15 000–30 000 m³";
  return "> 30 000 m³";
}

function fmtNum(n: number): string {
  return n.toLocaleString("es-BO");
}

/** Color-coded divIcon marker */
function makeDivIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:14px;height:14px;
      border-radius:50%;
      background:${color};
      border:2px solid #fff;
      box-shadow:0 1px 4px rgba(0,0,0,0.45);
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    popupAnchor: [0, -10],
  });
}

const ESTADO_COLOR: Record<string, string> = {
  ACTIVO: "#22c55e",
  INACTIVO: "#eab308",
  ERROR: "#ef4444",
};

function markerColor(estado: string): string {
  const key = estado.toUpperCase();
  return ESTADO_COLOR[key] ?? "#94a3b8";
}

// ---------------------------------------------------------------------------
// ClusterLayer – adds leaflet.markercluster layer imperatively
// ---------------------------------------------------------------------------
function ClusterLayer({
  data,
  filter,
}: {
  data: GatewayPoint[];
  filter: FilterType;
}) {
  const map = (window as any)._semapa_map as L.Map | undefined;

  useEffect(() => {
    if (!map) return;

    const filtered = data.filter((d) => {
      if (filter === "all") return true;
      if (filter === "activos") return d.estado.toUpperCase() === "ACTIVO";
      if (filter === "anomalias") return d.estado.toUpperCase() === "ERROR";
      if (filter === "morosos") return d.estado.toUpperCase() === "INACTIVO";
      return true;
    });

    // @ts-ignore
    const cluster = L.markerClusterGroup({
      maxClusterRadius: 60,
      iconCreateFunction: (c: any) => {
        const count = c.getChildCount();
        return L.divIcon({
          className: "",
          html: `<div style="
            width:36px;height:36px;
            border-radius:50%;
            background:rgba(29,78,216,0.85);
            color:#fff;
            font-size:13px;
            font-weight:700;
            display:flex;align-items:center;justify-content:center;
            border:2px solid #93c5fd;
            box-shadow:0 2px 8px rgba(0,0,0,0.35);
          ">${count}</div>`,
          iconSize: [36, 36],
          iconAnchor: [18, 18],
        });
      },
    });

    filtered.forEach((d) => {
      const color = markerColor(d.estado);
      const icon = makeDivIcon(color);
      const marker = L.marker([d.lat, d.lon], { icon });
      const lastReading = d.ultima_lectura ?? "—";
      marker.bindPopup(`
        <div style="min-width:160px;font-family:sans-serif;">
          <div style="font-weight:700;font-size:14px;margin-bottom:6px;border-bottom:1px solid #e2e8f0;padding-bottom:4px;">
            Medidor
          </div>
          <table style="font-size:12px;width:100%;border-collapse:collapse;">
            <tr><td style="color:#64748b;padding:2px 0;">MAC</td><td style="font-weight:600;padding-left:8px;">${d.mac}</td></tr>
            <tr><td style="color:#64748b;padding:2px 0;">Estado</td>
              <td style="padding-left:8px;">
                <span style="background:${color};color:#fff;padding:1px 6px;border-radius:9999px;font-size:11px;">${d.estado}</span>
              </td>
            </tr>
            <tr><td style="color:#64748b;padding:2px 0;">Última lectura</td><td style="padding-left:8px;">${lastReading}</td></tr>
          </table>
        </div>
      `);
      cluster.addLayer(marker);
    });

    map.addLayer(cluster);
    return () => {
      map.removeLayer(cluster);
    };
  }, [data, filter, map]);

  return null;
}

// ---------------------------------------------------------------------------
// MapRefCapture – store map ref on window for ClusterLayer
// ---------------------------------------------------------------------------
function MapRefCapture() {
  const map = useMap();
  useEffect(() => {
    (window as any)._semapa_map = map;
    return () => {
      (window as any)._semapa_map = undefined;
    };
  }, [map]);
  return null;
}

// ---------------------------------------------------------------------------
// Legend component (Leaflet control via portal-style div)
// ---------------------------------------------------------------------------
const LEGEND_ENTRIES = [
  { color: "#93c5fd", label: "< 1 000 m³" },
  { color: "#3b82f6", label: "1 000–5 000 m³" },
  { color: "#1d4ed8", label: "5 000–15 000 m³" },
  { color: "#1e3a8a", label: "15 000–30 000 m³" },
  { color: "#0f172a", label: "> 30 000 m³" },
];

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function Mapa() {
  const [filter, setFilter] = useState<FilterType>("all");
  const [selectedZone, setSelectedZone] = useState<ZoneStats | null>(null);
  const geoJsonRef = useRef<any>(null);

  // Meter / gateway points query
  const { data: gatewayData, isLoading } = useQuery({
    queryKey: ["mapa-medidores"],
    queryFn: async () => (await api.get("/consultas/cobertura-antenas")).data,
  });

  // Consumption per district query
  const { data: consumoData } = useQuery({
    queryKey: ["consumo-por-tarifa-distrito"],
    queryFn: async () => {
      try {
        return (await api.get("/consultas/consumo-por-tarifa-distrito")).data;
      } catch {
        return [];
      }
    },
  });

  const apiConsumption: any[] = consumoData ?? [];

  // Build gateway points with mock readings
  const MOCK_ESTADOS = ["ACTIVO", "ACTIVO", "ACTIVO", "INACTIVO", "ERROR"];
  const MOCK_DATES = ["2025-05-10", "2025-05-11", "2025-05-12", "2025-05-08", "2025-05-09"];

  const points: GatewayPoint[] = (gatewayData ?? []).map((g: any, idx: number) => ({
    lat: CENTRO[0] + ((idx % 9) - 4) * 0.008 + seedRandom(`lat${g.gateway_id}`) * 0.006,
    lon: CENTRO[1] + ((idx % 7) - 3) * 0.012 + seedRandom(`lon${g.gateway_id}`) * 0.008,
    mac: `GW-${String(g.gateway_id).padStart(4, "0")}`,
    estado: MOCK_ESTADOS[idx % MOCK_ESTADOS.length],
    ultima_lectura: MOCK_DATES[idx % MOCK_DATES.length],
  }));

  // GeoJSON style callback
  const zoneStyle = useCallback(
    (feature: any) => {
      const zona = feature?.properties?.zona ?? "";
      const consumo = consumptionForZone(zona, apiConsumption);
      return {
        fillColor: colorForConsumption(consumo),
        fillOpacity: 0.55,
        color: "#1e40af",
        weight: 1.5,
      };
    },
    [apiConsumption]
  );

  // GeoJSON interaction callbacks
  const onEachFeature = useCallback(
    (feature: any, layer: any) => {
      const props = feature.properties;
      const consumo = consumptionForZone(props.zona, apiConsumption);

      layer.on({
        mouseover: (e: any) => {
          e.target.setStyle({ fillOpacity: 0.75, weight: 2.5, color: "#60a5fa" });
          e.target.bringToFront();
        },
        mouseout: (e: any) => {
          e.target.setStyle({ fillOpacity: 0.55, weight: 1.5, color: "#1e40af" });
        },
        click: () => {
          setSelectedZone({
            zona: props.zona,
            distrito: props.distrito,
            medidores_ref: props.medidores_ref,
            consumo,
          });
        },
      });

      layer.bindTooltip(
        `<div style="font-weight:700;font-size:13px;">${props.zona}</div>
         <div style="font-size:12px;color:#475569;">${props.distrito} · ${fmtNum(consumo)} m³</div>`,
        { sticky: true, direction: "top", offset: [0, -6] }
      );
    },
    [apiConsumption]
  );

  // Filter button config
  const FILTER_BUTTONS: { key: FilterType; label: string; color: string }[] = [
    { key: "all", label: "Todos", color: "bg-blue-600 text-white" },
    { key: "activos", label: "Activos", color: "bg-green-600 text-white" },
    { key: "anomalias", label: "Anomalías", color: "bg-red-500 text-white" },
    { key: "morosos", label: "Morosos", color: "bg-yellow-500 text-white" },
  ];

  // Stats summary
  const totalPoints = points.length;
  const activeCount = points.filter((p) => p.estado === "ACTIVO").length;
  const errorCount = points.filter((p) => p.estado === "ERROR").length;
  const inactiveCount = points.filter((p) => p.estado === "INACTIVO").length;

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Page title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Mapa de Cobertura SEMAPA</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Cochabamba · {totalPoints} gateways representados · datos en tiempo real
          </p>
        </div>

        {/* Quick stats pills */}
        <div className="flex gap-2 text-xs font-medium">
          <span className="px-3 py-1 rounded-full bg-green-100 text-green-700">
            {activeCount} Activos
          </span>
          <span className="px-3 py-1 rounded-full bg-yellow-100 text-yellow-700">
            {inactiveCount} Inactivos
          </span>
          <span className="px-3 py-1 rounded-full bg-red-100 text-red-700">
            {errorCount} Errores
          </span>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex gap-2">
        {FILTER_BUTTONS.map((btn) => (
          <button
            key={btn.key}
            onClick={() => setFilter(btn.key)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all shadow-sm ${
              filter === btn.key
                ? btn.color + " ring-2 ring-offset-1 ring-blue-400 scale-105"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            {btn.label}
          </button>
        ))}
      </div>

      {/* Main content: map + side panel */}
      <div className="flex gap-4 flex-1 min-h-0" style={{ height: "calc(100vh - 200px)" }}>
        {/* Map */}
        <div className="flex-1 relative rounded-xl overflow-hidden shadow-lg border border-slate-200">
          <MapContainer center={CENTRO} zoom={13} style={{ height: "100%", width: "100%" }}>
            <MapRefCapture />
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            />

            {/* Choropleth zones */}
            <GeoJSON
              ref={geoJsonRef}
              key={JSON.stringify(apiConsumption)}
              data={ZONAS_CBB}
              style={zoneStyle}
              onEachFeature={onEachFeature}
            />

            {/* Cluster layer */}
            {!isLoading && <ClusterLayer data={points} filter={filter} />}

            {/* Legend – positioned bottom-left via absolute overlay */}
          </MapContainer>

          {/* Legend overlay */}
          <div
            className="absolute bottom-6 left-4 z-[1000] bg-white/95 backdrop-blur rounded-xl shadow-lg border border-slate-100 p-3"
            style={{ pointerEvents: "none" }}
          >
            <div className="text-xs font-bold text-slate-700 mb-2 flex items-center gap-1">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <circle cx="6" cy="6" r="5" fill="#1d4ed8" opacity="0.7" />
              </svg>
              Consumo por zona (m³)
            </div>
            {LEGEND_ENTRIES.map((e) => (
              <div key={e.label} className="flex items-center gap-2 mb-1">
                <div
                  className="w-4 h-3 rounded-sm flex-shrink-0"
                  style={{ background: e.color, border: "1px solid rgba(0,0,0,0.1)" }}
                />
                <span className="text-xs text-slate-600">{e.label}</span>
              </div>
            ))}
            <hr className="my-2 border-slate-100" />
            <div className="text-xs font-bold text-slate-700 mb-1">Medidores</div>
            {[
              { color: "#22c55e", label: "Activo" },
              { color: "#eab308", label: "Inactivo" },
              { color: "#ef4444", label: "Error" },
            ].map((e) => (
              <div key={e.label} className="flex items-center gap-2 mb-1">
                <div
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ background: e.color, border: "1px solid rgba(0,0,0,0.15)" }}
                />
                <span className="text-xs text-slate-600">{e.label}</span>
              </div>
            ))}
          </div>

          {/* Loading overlay */}
          {isLoading && (
            <div className="absolute inset-0 z-[999] bg-white/60 flex items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-slate-600 font-medium">Cargando datos…</span>
              </div>
            </div>
          )}
        </div>

        {/* Right panel */}
        <div className="w-80 flex flex-col gap-3 overflow-y-auto">
          {/* Zone info panel */}
          <div
            className={`bg-white rounded-xl shadow border border-slate-200 transition-all duration-300 ${
              selectedZone ? "opacity-100" : "opacity-60"
            }`}
          >
            <div className="p-4 border-b border-slate-100">
              <div className="flex items-center justify-between">
                <h2 className="font-bold text-slate-800 text-sm">Zona Seleccionada</h2>
                {selectedZone && (
                  <button
                    onClick={() => setSelectedZone(null)}
                    className="text-slate-400 hover:text-slate-600 text-xs"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            {selectedZone ? (
              <div className="p-4 space-y-3">
                <div>
                  <div className="text-lg font-bold text-blue-700">{selectedZone.zona}</div>
                  <div className="text-xs text-slate-400 font-medium uppercase tracking-wide mt-0.5">
                    {selectedZone.distrito}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-blue-50 rounded-lg p-2.5">
                    <div className="text-xs text-blue-500 font-medium">Medidores ref.</div>
                    <div className="text-lg font-bold text-blue-800">
                      {fmtNum(selectedZone.medidores_ref)}
                    </div>
                  </div>
                  <div className="bg-indigo-50 rounded-lg p-2.5">
                    <div className="text-xs text-indigo-500 font-medium">Consumo est.</div>
                    <div className="text-lg font-bold text-indigo-800">
                      {fmtNum(selectedZone.consumo)}
                    </div>
                    <div className="text-xs text-indigo-400">m³ / mes</div>
                  </div>
                </div>

                {/* Consumption bar */}
                <div>
                  <div className="flex justify-between text-xs text-slate-500 mb-1">
                    <span>Nivel de consumo</span>
                    <span className="font-medium">{labelForConsumption(selectedZone.consumo)}</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${Math.min(100, (selectedZone.consumo / 35000) * 100)}%`,
                        background: colorForConsumption(selectedZone.consumo),
                      }}
                    />
                  </div>
                </div>

                <a
                  href={`/consultas?zona=${encodeURIComponent(selectedZone.zona)}`}
                  className="block w-full text-center text-sm font-medium text-blue-600 border border-blue-200 rounded-lg py-2 hover:bg-blue-50 transition-colors"
                >
                  Ver detalle →
                </a>
              </div>
            ) : (
              <div className="p-4 text-center text-slate-400 text-sm py-8">
                <div className="text-3xl mb-2">🗺️</div>
                Haz clic en una zona del mapa para ver sus estadísticas
              </div>
            )}
          </div>

          {/* Zone summary table */}
          <div className="bg-white rounded-xl shadow border border-slate-200 flex-1">
            <div className="p-4 border-b border-slate-100">
              <h2 className="font-bold text-slate-800 text-sm">Resumen de Zonas</h2>
            </div>
            <div className="overflow-y-auto" style={{ maxHeight: "400px" }}>
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 uppercase text-[10px] tracking-wide">
                    <th className="text-left px-3 py-2 font-medium">Zona</th>
                    <th className="text-right px-3 py-2 font-medium">Consumo</th>
                  </tr>
                </thead>
                <tbody>
                  {ZONAS_CBB.features.map((f: any) => {
                    const consumo = consumptionForZone(f.properties.zona, apiConsumption);
                    const isSelected = selectedZone?.zona === f.properties.zona;
                    return (
                      <tr
                        key={f.properties.zona}
                        className={`border-t border-slate-50 cursor-pointer transition-colors ${
                          isSelected ? "bg-blue-50" : "hover:bg-slate-50"
                        }`}
                        onClick={() =>
                          setSelectedZone({
                            zona: f.properties.zona,
                            distrito: f.properties.distrito,
                            medidores_ref: f.properties.medidores_ref,
                            consumo,
                          })
                        }
                      >
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-1.5">
                            <div
                              className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                              style={{ background: colorForConsumption(consumo) }}
                            />
                            <span className={`font-medium ${isSelected ? "text-blue-700" : "text-slate-700"}`}>
                              {f.properties.zona}
                            </span>
                          </div>
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-slate-600">
                          {fmtNum(consumo)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Marker status breakdown */}
          <div className="bg-white rounded-xl shadow border border-slate-200 p-4">
            <h2 className="font-bold text-slate-800 text-sm mb-3">Estado de Gateways</h2>
            <div className="space-y-2">
              {[
                { label: "Activos", count: activeCount, color: "#22c55e", bg: "bg-green-50", text: "text-green-700" },
                { label: "Inactivos", count: inactiveCount, color: "#eab308", bg: "bg-yellow-50", text: "text-yellow-700" },
                { label: "Con error", count: errorCount, color: "#ef4444", bg: "bg-red-50", text: "text-red-700" },
              ].map((s) => (
                <div key={s.label} className={`flex items-center justify-between rounded-lg px-3 py-2 ${s.bg}`}>
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ background: s.color }}
                    />
                    <span className={`text-xs font-medium ${s.text}`}>{s.label}</span>
                  </div>
                  <span className={`text-sm font-bold ${s.text}`}>{s.count}</span>
                </div>
              ))}
              {totalPoints === 0 && (
                <p className="text-xs text-slate-400 text-center py-2">
                  No hay datos de gateways disponibles
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

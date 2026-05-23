import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import "leaflet.markercluster";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useThemeStore } from "../store/theme";

const CENTRO: [number, number] = [-17.39, -66.13];

const TILES = {
  light: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
};

interface DistritoGeo { distrito_id: number; nombre: string; medidores: number; consumo_m3: number; }
interface ZonaInfo { zona: string; medidores: number; consumo_m3: number; }
interface Medidor {
  mac: string; numero_contrato: string; titular: string; categoria: string;
  subcategoria: string; estado: string; activo: boolean; zona: string;
  lat: number; lon: number;
}

function colorEstado(activo: boolean, estado: string): string {
  if (estado === "Dañado") return "#ef4444";
  if (estado === "Mantenimiento") return "#eab308";
  return activo ? "#22c55e" : "#94a3b8";
}
function colorConsumo(v: number, max: number): string {
  const t = max ? v / max : 0;
  if (t > 0.8) return "#0f172a";
  if (t > 0.6) return "#1e3a8a";
  if (t > 0.4) return "#1d4ed8";
  if (t > 0.2) return "#3b82f6";
  return "#93c5fd";
}

function MapRef({ onReady }: { onReady: (m: L.Map) => void }) {
  const map = useMap();
  useEffect(() => { onReady(map); }, [map, onReady]);
  return null;
}

export default function Mapa() {
  const theme = useThemeStore((s) => s.theme);
  const [map, setMap] = useState<L.Map | null>(null);
  const [distritoSel, setDistritoSel] = useState<number | null>(null);
  const [zonaSel, setZonaSel] = useState<string>("");
  const [usoSel, setUsoSel] = useState<string>("");
  const [macSel, setMacSel] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  // GeoJSON distritos (real)
  const { data: distritosGeo } = useQuery({
    queryKey: ["distritos-geojson"],
    queryFn: async () => (await fetch("/distritos.geojson")).json(),
  });

  // GeoJSON zonas (convex hulls)
  const { data: zonasGeo } = useQuery({
    queryKey: ["zonas-geojson"],
    queryFn: async () => (await fetch("/zonas.geojson")).json(),
  });

  // Stats consumo por distrito (choropleth)
  const { data: geo } = useQuery<DistritoGeo[]>({
    queryKey: ["mapa-geo"],
    queryFn: async () => (await api.get("/mapa/distritos-geo")).data,
  });

  // Catálogo usos de suelo
  const { data: usos } = useQuery<string[]>({
    queryKey: ["usos-suelo"],
    queryFn: async () => (await api.get("/mapa/usos-suelo")).data,
  });

  // Zonas del distrito seleccionado
  const { data: zonas } = useQuery<ZonaInfo[]>({
    queryKey: ["mapa-zonas", distritoSel],
    queryFn: async () => (await api.get(`/mapa/distrito/${distritoSel}/zonas`)).data,
    enabled: distritoSel !== null,
  });

  // Medidores (al elegir zona)
  const { data: medidores, isFetching: loadingMed } = useQuery({
    queryKey: ["mapa-medidores", distritoSel, zonaSel, usoSel],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (zonaSel) params.set("zona", zonaSel);
      if (usoSel) params.set("uso_suelo", usoSel);
      params.set("limite", "3000");
      return (await api.get(`/mapa/distrito/${distritoSel}/medidores?${params}`)).data;
    },
    enabled: distritoSel !== null && (!!zonaSel || !!usoSel),
  });

  const { data: detalle, isFetching: loadingDet } = useQuery({
    queryKey: ["mapa-detalle", macSel],
    queryFn: async () => (await api.get(`/mapa/medidor/${macSel}`)).data,
    enabled: macSel !== null,
  });

  const consumoMap = useMemo(() => {
    const m: Record<number, DistritoGeo> = {};
    (geo || []).forEach((d) => (m[d.distrito_id] = d));
    return m;
  }, [geo]);
  const maxCons = Math.max(1, ...(geo || []).map((d) => d.consumo_m3));

  // ===== Estilo capa distritos =====
  function styleDistrito(feature: any) {
    const id = feature.properties.distrito;
    const cons = consumoMap[id]?.consumo_m3 || 0;
    const selected = distritoSel === id;
    return {
      color: selected ? "#0ea5e9" : (theme === "dark" ? "#64748b" : "#475569"),
      weight: selected ? 3 : 1.2,
      fillColor: colorConsumo(cons, maxCons),
      fillOpacity: selected ? 0.15 : 0.35,
    };
  }
  function onEachDistrito(feature: any, layer: any) {
    const id = feature.properties.distrito;
    const info = consumoMap[id];
    layer.bindTooltip(
      `Distrito ${id} · ${(info?.consumo_m3 || 0).toLocaleString()} m³ · ${info?.medidores || 0} med.`,
      { sticky: true });
    layer.on("click", () => {
      setDistritoSel(id);
      setZonaSel("");
      setMacSel(null);
      if (map) map.fitBounds(layer.getBounds(), { padding: [30, 30] });
    });
  }

  // ===== Estilo capa zonas (solo si hay distrito sel) =====
  const zonaStats = useMemo(() => {
    const m: Record<string, ZonaInfo> = {};
    (zonas || []).forEach((z) => (m[z.zona] = z));
    return m;
  }, [zonas]);
  const maxZonaCons = Math.max(1, ...(zonas || []).map((z) => z.consumo_m3));

  function styleZona(feature: any) {
    const z = (feature.properties.zona || "").trim();
    const sel = z === zonaSel;
    const cons = zonaStats[z]?.consumo_m3 || 0;
    return {
      color: sel ? "#f59e0b" : "#0ea5e9",
      weight: sel ? 3 : 1.5,
      fillColor: colorConsumo(cons, maxZonaCons),
      fillOpacity: sel ? 0.55 : 0.35,
      dashArray: sel ? undefined : "3 4",
    };
  }
  function onEachZona(feature: any, layer: any) {
    const z = (feature.properties.zona || "").trim();
    const info = zonaStats[z];
    layer.bindTooltip(
      `${z}` + (info ? ` · ${info.medidores} med. · ${info.consumo_m3.toLocaleString()} m³` : ""),
      { sticky: true });
    layer.on("click", () => {
      setZonaSel(z);
      setMacSel(null);
      if (map) map.fitBounds(layer.getBounds(), { padding: [30, 30] });
    });
  }

  // Filtra zonasGeo por distrito seleccionado
  const zonasGeoFiltered = useMemo(() => {
    if (!zonasGeo || distritoSel === null) return null;
    return {
      type: "FeatureCollection",
      features: (zonasGeo.features || []).filter(
        (f: any) => f.properties.distrito === distritoSel
      ),
    };
  }, [zonasGeo, distritoSel]);

  // ===== Markers medidores =====
  useEffect(() => {
    if (!map || !medidores?.medidores) return;
    // @ts-ignore
    const cluster = L.markerClusterGroup({ maxClusterRadius: 50 });
    const pts: Medidor[] = medidores.medidores;
    pts.forEach((m) => {
      const icon = L.divIcon({
        className: "",
        html: `<div style="width:13px;height:13px;border-radius:50%;background:${colorEstado(m.activo, m.estado)};border:2px solid white;box-shadow:0 0 3px rgba(0,0,0,.4)"></div>`,
        iconSize: [13, 13],
      });
      const mk = L.marker([m.lat, m.lon], { icon });
      mk.bindPopup(
        `<b>${m.mac}</b><br/>${m.numero_contrato || "s/contrato"}<br/>${m.titular || ""}<br/>` +
        `${m.subcategoria} · ${m.estado}<br/>` +
        `<button class="ver-med-btn" data-mac="${m.mac}" style="margin-top:6px;padding:4px 10px;background:#0ea5e9;color:white;border:none;border-radius:4px;cursor:pointer">Ver más info</button>`
      );
      mk.on("popupopen", () => {
        document.querySelectorAll<HTMLButtonElement>(".ver-med-btn").forEach((b) => {
          b.onclick = (e) => {
            e.preventDefault();
            setMacSel(b.dataset.mac || null);
            setModalOpen(true);
          };
        });
      });
      cluster.addLayer(mk);
    });
    map.addLayer(cluster);
    return () => { map.removeLayer(cluster); };
  }, [map, medidores]);

  // Cambio distrito por combo
  function onDistritoChange(idStr: string) {
    const id = idStr ? parseInt(idStr, 10) : null;
    setDistritoSel(id);
    setZonaSel("");
    setMacSel(null);
    if (map && distritosGeo && id !== null) {
      const ft = distritosGeo.features.find((f: any) => f.properties.distrito === id);
      if (ft) {
        const layer = L.geoJSON(ft);
        map.fitBounds(layer.getBounds(), { padding: [30, 30] });
      }
    } else if (map && id === null) {
      map.setView(CENTRO, 12);
    }
  }
  function onZonaChange(z: string) {
    setZonaSel(z);
    setMacSel(null);
    if (map && zonasGeo && z) {
      const ft = zonasGeo.features.find(
        (f: any) => f.properties.distrito === distritoSel && f.properties.zona === z
      );
      if (ft) {
        const layer = L.geoJSON(ft);
        map.fitBounds(layer.getBounds(), { padding: [30, 30] });
      }
    }
  }

  return (
    <div className="space-y-2">
      {/* Top bar — combos */}
      <div className="bg-white dark:bg-slate-800 rounded-lg border shadow-sm p-3 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[200px]">
          <label className="text-xs uppercase text-slate-500 font-semibold block mb-1">Distrito</label>
          <select
            value={distritoSel ?? ""}
            onChange={(e) => onDistritoChange(e.target.value)}
            className="w-full border rounded px-2 py-1.5 bg-white dark:bg-slate-700">
            <option value="">— Todos los distritos —</option>
            {(geo || []).slice().sort((a, b) => a.distrito_id - b.distrito_id).map((d) => (
              <option key={d.distrito_id} value={d.distrito_id}>
                {d.nombre} ({d.medidores.toLocaleString()} med.)
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 min-w-[200px]">
          <label className="text-xs uppercase text-slate-500 font-semibold block mb-1">Zona</label>
          <select
            value={zonaSel}
            onChange={(e) => onZonaChange(e.target.value)}
            disabled={distritoSel === null}
            className="w-full border rounded px-2 py-1.5 bg-white dark:bg-slate-700 disabled:opacity-50">
            <option value="">— {distritoSel === null ? "Elige distrito primero" : "Todas las zonas"} —</option>
            {(zonas || []).map((z) => (
              <option key={z.zona} value={z.zona}>
                {z.zona} ({z.medidores} med.)
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 min-w-[200px]">
          <label className="text-xs uppercase text-slate-500 font-semibold block mb-1">Uso de suelo</label>
          <select
            value={usoSel}
            onChange={(e) => setUsoSel(e.target.value)}
            className="w-full border rounded px-2 py-1.5 bg-white dark:bg-slate-700">
            <option value="">— Todos —</option>
            {(usos || []).map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </div>

        <button
          onClick={() => { setDistritoSel(null); setZonaSel(""); setUsoSel(""); setMacSel(null); if (map) map.setView(CENTRO, 12); }}
          className="px-3 py-1.5 border rounded text-sm bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600">
          Limpiar filtros
        </button>
      </div>

      {/* Mapa fullscreen */}
      <div className="rounded-lg overflow-hidden shadow border relative" style={{ height: "calc(100vh - 200px)" }}>
        {loadingMed && (
          <div className="absolute top-2 right-2 z-[1000] bg-white px-3 py-1 rounded shadow text-xs">
            Cargando medidores...
          </div>
        )}
        <MapContainer center={CENTRO} zoom={12} style={{ height: "100%", width: "100%" }}>
          <MapRef onReady={setMap} />
          <TileLayer key={theme} url={theme === "dark" ? TILES.dark : TILES.light}
            subdomains="abcd" attribution='&copy; OpenStreetMap &copy; CARTO' />

          {/* Capa distritos siempre visible */}
          {distritosGeo && (
            <GeoJSON
              key={`distritos-${distritoSel}-${theme}-${!!geo}`}
              data={distritosGeo}
              style={styleDistrito as any}
              onEachFeature={onEachDistrito}
            />
          )}

          {/* Capa zonas — solo si hay distrito seleccionado */}
          {zonasGeoFiltered && (
            <GeoJSON
              key={`zonas-${distritoSel}-${zonaSel}-${theme}`}
              data={zonasGeoFiltered as any}
              style={styleZona as any}
              onEachFeature={onEachZona}
            />
          )}
        </MapContainer>

        {/* Leyenda */}
        <div className="absolute bottom-2 left-2 z-[1000] bg-white/95 dark:bg-slate-800/95 px-3 py-2 rounded shadow text-[11px] space-y-1">
          <div className="font-semibold">Choropleth consumo</div>
          <div><span className="inline-block w-3 h-3 mr-1" style={{ background: "#93c5fd" }} />bajo</div>
          <div><span className="inline-block w-3 h-3 mr-1" style={{ background: "#1e3a8a" }} />alto</div>
          <hr className="my-1" />
          <div><span className="inline-block w-3 h-3 rounded-full bg-green-500 mr-1" />Operativo</div>
          <div><span className="inline-block w-3 h-3 rounded-full bg-yellow-500 mr-1" />Mantenimiento</div>
          <div><span className="inline-block w-3 h-3 rounded-full bg-red-500 mr-1" />Dañado</div>
        </div>

        {/* Info filtros activos */}
        {(distritoSel !== null || zonaSel || usoSel) && (
          <div className="absolute top-2 left-2 z-[1000] bg-white/95 dark:bg-slate-800/95 px-3 py-2 rounded shadow text-xs space-y-1 max-w-xs">
            <div className="font-semibold">Filtros activos</div>
            {distritoSel !== null && <div>📍 Distrito: {consumoMap[distritoSel]?.nombre || distritoSel}</div>}
            {zonaSel && <div>🏘️ Zona: {zonaSel}</div>}
            {usoSel && <div>🏷️ Uso: {usoSel}</div>}
            {medidores && <div className="text-slate-500 mt-1">{medidores.total} medidores visibles</div>}
          </div>
        )}
      </div>

      {/* MODAL detalle medidor */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-[2000] bg-black/50 flex items-center justify-center p-4"
          onClick={() => setModalOpen(false)}>
          <div
            className="bg-white dark:bg-slate-800 rounded-lg shadow-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center px-5 py-3 border-b sticky top-0 bg-white dark:bg-slate-800 z-10">
              <h2 className="font-bold text-lg">Detalle del medidor</h2>
              <button
                onClick={() => setModalOpen(false)}
                className="text-2xl text-slate-400 hover:text-slate-700">×</button>
            </div>
            <div className="p-5">
              {loadingDet && <p className="text-sm text-slate-500">Cargando...</p>}
              {detalle && (
                <div className="space-y-4 text-sm">
                  <div>
                    <div className="text-xs uppercase text-slate-400 font-semibold">Medidor</div>
                    <div className="font-mono font-bold text-base">{detalle.medidor?.mac}</div>
                    <div className="text-xs">Estado: <b>{detalle.medidor?.estado}</b> · Modelo {detalle.medidor?.tipo_medidor_id}</div>
                  </div>
                  {detalle.contrato && (
                    <div className="bg-slate-50 dark:bg-slate-700 rounded p-3">
                      <div className="text-xs uppercase text-slate-400 font-semibold mb-1">Contrato</div>
                      <div className="font-bold">{detalle.contrato.numero_contrato}</div>
                      <div>{detalle.contrato.titular_contrato}</div>
                      <div className="text-xs text-slate-500">CI: {detalle.contrato.ci_titular}</div>
                      <div className="text-xs">{detalle.contrato.categoria} ({detalle.contrato.subcategoria})</div>
                      <div className="text-xs text-slate-500">Estado: {detalle.contrato.estado_contrato}</div>
                    </div>
                  )}
                  {detalle.infraestructura && (
                    <div className="bg-slate-50 dark:bg-slate-700 rounded p-3">
                      <div className="text-xs uppercase text-slate-400 font-semibold mb-1">Infraestructura</div>
                      <div className="text-sm">{detalle.infraestructura.direccion}</div>
                      <div className="text-xs text-slate-500">
                        Zona: {detalle.infraestructura.zona} · Distrito: {detalle.infraestructura.distrito_id}
                      </div>
                      {detalle.infraestructura.uso_suelo && (
                        <div className="text-xs"><b>Uso de suelo:</b> {detalle.infraestructura.uso_suelo}</div>
                      )}
                      <div className="text-xs text-slate-500">
                        Sup: {detalle.infraestructura.superficie_terreno} m² · Constr: {detalle.infraestructura.area_construida} m²
                      </div>
                    </div>
                  )}
                  <div>
                    <div className="text-xs uppercase text-slate-400 font-semibold mb-2">Consumo reciente</div>
                    <table className="w-full text-xs">
                      <thead className="bg-slate-100 dark:bg-slate-700">
                        <tr>
                          <th className="text-left p-1.5">Periodo</th>
                          <th className="text-right p-1.5">m³</th>
                          <th className="text-right p-1.5">Lectura</th>
                          <th className="text-center p-1.5">Pago</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(detalle.lecturas || []).map((l: any, i: number) => (
                          <tr key={i} className="border-t">
                            <td className="p-1.5">{l.periodo}</td>
                            <td className="text-right font-mono p-1.5">{l.consumo_m3}</td>
                            <td className="text-right font-mono p-1.5">{l.lectura_actual}</td>
                            <td className="text-center p-1.5">{l.pagado ? "✅" : "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

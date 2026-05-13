import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import { useEffect, useState } from "react";
import L from "leaflet";
import "leaflet.markercluster";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

// Centroide de Cochabamba aproximado
const CENTRO: [number, number] = [-17.39, -66.15];

function ClusterLayer({ data }: { data: { lat: number; lon: number; mac: string; estado: string }[] }) {
  const map = (window as any)._semapa_map as L.Map | undefined;
  useEffect(() => {
    if (!map) return;
    // @ts-ignore
    const cluster = L.markerClusterGroup({ maxClusterRadius: 60 });
    data.forEach((d) => {
      const m = L.marker([d.lat, d.lon]);
      m.bindPopup(`<div><b>${d.mac}</b><br/>estado=${d.estado}</div>`);
      cluster.addLayer(m);
    });
    map.addLayer(cluster);
    return () => {
      map.removeLayer(cluster);
    };
  }, [data, map]);
  return null;
}

export default function Mapa() {
  const { data, isLoading } = useQuery({
    queryKey: ["mapa-medidores"],
    queryFn: async () => (await api.get("/consultas/cobertura-antenas")).data,
  });

  // Mock simplificado: usamos gateways para colocar puntos representativos
  // En prod: endpoint dedicado paginado /medidores?zona=...
  const points = (data || []).map((g: any, idx: number) => ({
    lat: CENTRO[0] + (idx - 2) * 0.01,
    lon: CENTRO[1] + (idx - 2) * 0.015,
    mac: `gateway-${g.gateway_id}`,
    estado: `medidores=${g.medidores}`,
  }));

  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold">Mapa de cobertura</h1>
      <p className="text-sm text-slate-500">
        Clustering activado · {points.length} elementos representados (gateways).
      </p>
      <div className="h-[70vh] rounded-lg overflow-hidden shadow border">
        <MapContainer
          center={CENTRO}
          zoom={13}
          ref={(m) => { if (m) (window as any)._semapa_map = m; }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; OpenStreetMap'
          />
          {!isLoading && <ClusterLayer data={points} />}
          {points.map((p: { lat: number; lon: number; mac: string; estado: string }, i: number) => (
            <Marker key={i} position={[p.lat, p.lon]}>
              <Popup>
                <b>{p.mac}</b><br />
                {p.estado}
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}

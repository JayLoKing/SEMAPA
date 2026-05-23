"""Genera zonas.geojson con polígonos limpios por (distrito, zona).

Estrategia: Voronoi diagram de los centroides de cada zona, recortado
por el polígono real del distrito padre. Resultado: celdas contiguas
sin solapamiento que rellenan todo el distrito (apariencia de barrios reales).

Entradas:
  - Tabla `infraestructuras` (lat/lon/zona/distrito_id)
  - /data/distritos.geojson (polígonos reales del distrito)

Salida: /data/zonas.geojson  (copiar manual a web/public/)
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

from loguru import logger
from shapely.geometry import MultiPoint, Point, shape, mapping
from shapely.ops import voronoi_diagram, unary_union

from cassandra_io import connect


OUT_PATH = os.getenv("ZONAS_GEO_OUT", "/data/zonas.geojson")
DISTRITOS_PATH = os.getenv("DISTRITOS_GEO", "/data/distritos.geojson")


def load_distritos() -> dict[int, "Polygon"]:
    """Devuelve {distrito_id: shapely_polygon} desde el GeoJSON oficial."""
    with open(DISTRITOS_PATH, encoding="utf-8") as f:
        gj = json.load(f)
    out = {}
    for ft in gj["features"]:
        d = ft["properties"].get("distrito")
        if d is not None:
            out[d] = shape(ft["geometry"])
    return out


def main():
    cluster, session = connect()

    # 1. Cargar polígonos reales de distritos
    distritos = load_distritos()
    logger.info(f"Distritos cargados: {sorted(distritos.keys())}")

    # 2. Agrupar puntos de infraestructuras por (distrito, zona)
    coords: dict[tuple[int, str], list[tuple[float, float]]] = defaultdict(list)
    usos: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    n_in = 0
    logger.info("Leyendo infraestructuras...")
    for r in session.execute(
        "SELECT distrito_id, zona, latitud, longitud, uso_suelo FROM infraestructuras"
    ):
        d = r.distrito_id
        z = (r.zona or "").strip()
        lat = r.latitud
        lon = r.longitud
        if d is None or not z or lat is None or lon is None:
            continue
        if d not in distritos:
            continue
        coords[(d, z)].append((lon, lat))
        usos[(d, z)][(r.uso_suelo or "").strip()] += 1
        n_in += 1
    logger.info(f"Puntos: {n_in:,} | zonas únicas: {len(coords):,}")

    # 3. Por cada distrito → centroide zona → Voronoi clipped
    features = []
    # agrupar zonas por distrito
    por_distrito: dict[int, list[tuple[str, tuple[float, float], int]]] = defaultdict(list)
    for (d, z), pts in coords.items():
        if len(pts) < 1:
            continue
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        por_distrito[d].append((z, (cx, cy), len(pts)))

    for d, zonas in por_distrito.items():
        poly_d = distritos[d]
        if len(zonas) == 1:
            # 1 sola zona → toma todo el distrito
            z, _, n = zonas[0]
            features.append(_feature(d, z, poly_d, n, usos[(d, z)]))
            continue

        # MultiPoint de centroides
        pts = [Point(c[0], c[1]) for _, c, _ in zonas]
        try:
            vd = voronoi_diagram(MultiPoint(pts), envelope=poly_d)
        except Exception as e:
            logger.warning(f"voronoi fallo distrito {d}: {e} — fallback convex hull")
            for z, _, n in zonas:
                hull = MultiPoint(coords[(d, z)]).convex_hull
                if hull.geom_type == "Point":
                    hull = hull.buffer(0.0008)
                features.append(_feature(d, z, hull.intersection(poly_d), n, usos[(d, z)]))
            continue

        # Cada celda voronoi → asignar a la zona del centroide que contiene
        for cell in vd.geoms:
            # encontrar centroide dentro de la celda
            assigned = None
            for i, (z, c, n) in enumerate(zonas):
                if cell.contains(Point(c[0], c[1])):
                    assigned = (z, n)
                    break
            if assigned is None:
                continue
            clipped = cell.intersection(poly_d)
            if clipped.is_empty:
                continue
            features.append(_feature(d, assigned[0], clipped, assigned[1], usos[(d, assigned[0])]))

    gj = {"type": "FeatureCollection", "features": features}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(gj, f, ensure_ascii=False)
    logger.success(f"OK: {OUT_PATH} | features={len(features)} (Voronoi clipped por distrito)")
    cluster.shutdown()


def _feature(distrito, zona, geom, n_pts, usos_dict):
    uso_top = max(usos_dict.items(), key=lambda x: x[1])[0] if usos_dict else ""
    return {
        "type": "Feature",
        "properties": {
            "distrito": distrito,
            "zona": zona,
            "puntos": n_pts,
            "uso_top": uso_top,
        },
        "geometry": mapping(geom),
    }


if __name__ == "__main__":
    main()

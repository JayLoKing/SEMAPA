# 📊 Progreso del Proyecto SEMAPA

> Se actualiza al final de cada fase: tareas, archivos, verificación, resultados.

---

## ✅ Fase 0 — Repositorio y .gitignore

- `git` inicializado, branch `main`.
- `.gitignore` raíz exhaustivo (Python/Node/Expo/Docker/secrets).
- `.dockerignore` por servicio.
- `.env.example` con todas las variables.
- `README.md`, `LICENSE` (MIT), `CONTRIBUTING.md`.
- `.github/workflows/ci.yml`.

---

## ✅ Fase 1 — Infraestructura y schema Cassandra

- `docker-compose.yml`: cluster Cassandra 2 nodos + Redis + RabbitMQ + Mailhog +
  Nginx + 2 réplicas API + workers + pdf-service + web + seeder + simulator + ingestor.
- Schema CQL: keyspace `SimpleStrategy` RF=2 + 16 tablas + índices.
- `lecturas_por_medidor` con `LZ4Compressor` + `TimeWindowCompactionStrategy` (ventana 7 días).
- Nginx reverse proxy + `least_conn` + gzip + security headers.
- RabbitMQ: exchange topic `semapa.notifications` + DLQ.
- `docker compose config --quiet` ✅

---

## ✅ Fase 2 — Seeder

Archivos:
- `services/seeder/excel_loader.py`, `cassandra_io.py`, `csv_writer.py`
- `services/seeder/seed.py`: catálogos + 3 usuarios bcrypt + 85k personas +
  100k+ infra + 120k medidores.
- `services/seeder/seed_lecturas.py`: ~15M+ lecturas 2025-04-01→hoy.
- `docker build` ✅ + imports verificados.

Ejecutar (cluster activo):
```bash
docker compose --profile tools run --rm seeder python -u seed.py
docker compose --profile tools run --rm seeder python -u seed_lecturas.py
```

---

## ✅ Fase 3 — Simulator + Ingestor

- `services/simulator/simulator.py`: FastAPI + loop horario, genera `.txt`
  en `/lora-data/{gateway}/{YYYY-MM-DD-HH}/{mac}.txt`. POST `/simulate/burst`.
  0.5 % errores + 0.07 % duplicados. Puerto 8002.
- `services/ingestor/ingestor.py`: watchdog (PollingObserver) + dedup Redis
  (TTL 24h) + LRU cache de macs + inserciones concurrentes. Métricas HTTP 8003.

Build + smoke ✅.

---

## ✅ Fase 4 — Backend API

- Cassandra singleton (TokenAware+DCAware, `LOCAL_QUORUM`, profile `analytics`=ONE).
- Redis cliente async (cache + rate limit).
- Security: JWT (PyJWT), bcrypt, OAuth2 bearer, role guards.
- Middleware: JSON logs + rate limit Redis (200/min/IP).
- USD service: exchangerate.host + fallback + cache 15 min.
- Routers: `auth`, `dashboard`, `consultas` (26 endpoints), `facturas`, `notify`
  (aio-pika), `usd`, `buscar`, `lecturas` (mobile).
- 38 rutas registradas. Tests: 33 verde.

---

## ✅ Fase 5 — PDF Service

- ReportLab: media carta A5 (cliente, tramos, totales, QR, Code128) y rollo
  térmico 80 mm (compacto, QR).
- `GET /pdf` y `POST /pdf/batch` (ZIP).
- 10 PDFs muestra en `docs/img/samples/` (5 categorías × 2 formatos).

---

## ✅ Fase 6 — Workers de notificación

- `worker-email`: consume `notify.email`, busca factura + persona, descarga
  2 PDFs del pdf-service, SMTP a Mailhog con adjuntos.
- `worker-sms` y `worker-whatsapp`: mocks que loguean.
- 3 reintentos exponenciales (header `x-retries`) → DLX `notify.dlq`.

Build + import ✅ los 3.

---

## ✅ Fase 7 — Frontend Web

- React 18 + Vite + TS + Tailwind + TanStack Query + Zustand + React Router.
- Páginas: Login, Dashboard (KPIs + charts), Mapa (Leaflet + markercluster),
  Consultas (grid 25 botones), Facturación (búsqueda + lote + canales notify),
  DetalleMedidor.
- Optimizaciones: `React.lazy`, Vite `manualChunks` (react/leaflet/charts).
- Docker build OK (nginx:alpine).

---

## ✅ Fase 8 — Documentación

- `docs/arquitectura.md` (diagrama componentes y flujos)
- `docs/conceptos-cassandra.md` (glosario evaluación)
- `docs/informe-tecnico.md` (≤2 páginas)
- `docs/reglamento-tarifario.md` (resumen del PDF)
- `docs/api.md` (todos los endpoints)

---

## ✅ Fase 9 — Mobile (Expo + React Native)

- Pantallas: Login (secure-store), Home (geo + 5 medidores Univalle ordenados
  haversine), Lectura (POST `/lecturas/manual`), Historial.
- Tech: expo SDK 50, react-navigation, react-native-maps, axios, zustand.

---

## ✅ Fase 10 — Reglamento Tarifario

- `services/api/app/services/tarifa_service.py`: 9 categorías + cargo fijo +
  6 tramos progresivos + reglas especiales (Arts. 6, 7, 9, 10, 13, 14, 15,
  16, 17, 18, 20, 21, 22, 24) + factor K + multa K10.
- 31 tests unitarios verde.

---

## Checklist final

- [x] Repositorio limpio (sin `.env`, sin `node_modules`)
- [x] `docker compose config` ✅
- [x] 38 rutas API operativas
- [x] 26 consultas analíticas (25 + extras)
- [x] PDFs generados (5 categorías × 2 formatos)
- [x] Workers email/SMS/WhatsApp listos
- [x] App móvil con geolocalización funcional
- [x] Reglamento tarifario completo + tests
- [x] Documentación técnica + glosario Cassandra
- [x] CI/CD workflow GitHub Actions

## Pendiente de ejecución end-to-end (requiere host con recursos)

- [ ] `docker compose up -d` y validar 2 nodos UN en `nodetool status`
- [ ] Correr seeder + seed_lecturas → verificar conteos
- [ ] Ejercitar las 25 consultas vía Swagger
- [ ] Test E2E mobile contra backend real

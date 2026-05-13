# 📊 Progreso del Proyecto SEMAPA

> Se actualiza al final de cada fase: tareas, archivos, verificación, resultados.

---

## Fase 0 — Repositorio y .gitignore

**Estado:** ✅ Completada

- `git` inicializado
- `.gitignore` raíz exhaustivo
- `.dockerignore` por servicio (api, ingestor, pdf-service, seeder, simulator, workers, web)
- `.env.example` con todas las variables
- `README.md`, `LICENSE` (MIT), `CONTRIBUTING.md`
- `.github/workflows/ci.yml`

**Verificación:** `git status` limpio.

---

## Fase 1 — Infraestructura y schema Cassandra

**Estado:** ✅ Completada (código). Ejecución validada parcialmente: `docker compose config` OK.

- `docker-compose.yml`: cluster Cassandra 2 nodos + Redis + RabbitMQ + Mailhog +
  Nginx + 2 réplicas API + workers + pdf-service + web + seeder + simulator +
  ingestor.
- Schema CQL: keyspace (`SimpleStrategy` RF=2) + 16 tablas + índices secundarios.
- `lecturas_por_medidor` con `LZ4Compressor` + `TimeWindowCompactionStrategy`
  (ventana de 7 días) → particiones < 100 MB.
- Nginx reverse proxy + `least_conn` load balancer + gzip + security headers.
- RabbitMQ definitions: exchange topic `semapa.notifications` + DLQ.

**Verificación pendiente (ejecutar con Docker activo):**

```bash
docker compose up -d
docker exec semapa-cassandra-1 nodetool status
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; DESCRIBE TABLES;"
```

---

## Fase 2 — Seeder

**Estado:** ✅ Código completado. Build Docker validado. Ejecución contra cluster pendiente.

**Archivos:**
- `services/seeder/excel_loader.py` — parseo del Excel con forward-fill jerárquico,
  DMS→decimal para gateways, mapeo categorías R1..S.
- `services/seeder/cassandra_io.py` — cluster con `TokenAwarePolicy`
  (`DCAwareRoundRobinPolicy`), `LOCAL_QUORUM`, prepared statements,
  `execute_concurrent_with_args`.
- `services/seeder/csv_writer.py` — CSVs derivados en `data/seeds/`.
- `services/seeder/seed.py` — catálogos + 3 usuarios (bcrypt cost=12) + 85 000
  personas (80k naturales + 5k jurídicas) + 100 000+ infraestructuras +
  120 000 medidores con jitter de coordenadas, modelo según distribución, estado
  95/3/2%, número de contrato secuencial, MAC y serie aleatorios.
- `services/seeder/seed_lecturas.py` — time-series 2025-04-01..hoy, 3
  lecturas/día por medidor, residenciales con bloques 0-1300/0-380/0-190 L,
  acumulado monótono, 0.5 % errores (status 3..9), inserta en
  `lecturas_por_medidor` + `lecturas_por_zona_dia`.
- `services/seeder/Dockerfile` — multi-stage, `--prefix=/install` para
  permisos correctos en `appuser`, `libev` para `cassandra-driver`.
- `docker-compose.yml`: volumen `./Recursos Practica 5.xlsx:/recursos/recursos.xlsx:ro`.

**Verificación realizada:**
- `docker compose config --quiet` ✅
- `docker build ./services/seeder` ✅
- `docker run … python -c "import seed, seed_lecturas, …"` ✅

**Comandos para ejecutar con el cluster levantado:**

```bash
docker compose --profile tools run --rm seeder python -u seed.py
docker compose --profile tools run --rm seeder python -u seed_lecturas.py
docker exec semapa-cassandra-1 cqlsh -e "
SELECT COUNT(*) FROM semapa.personas;
SELECT COUNT(*) FROM semapa.medidores;
SELECT COUNT(*) FROM semapa.infraestructuras;
"
```

**Tiempos estimados:**
- `seed.py`: 5–15 min
- `seed_lecturas.py`: 30–60 min (`LECTURAS_CONCURRENCY=200`, `LECTURAS_BATCH=5000`)

---

## Fase 3 — Simulador + Ingestor

**Estado:** ⏳ Pendiente

---

## Fase 4 — Backend API

**Estado:** ⏳ Pendiente (estructura base + `/health` listos)

---

## Fase 5 — PDF Service

**Estado:** ⏳ Pendiente

---

## Fase 6 — Workers de notificación

**Estado:** ⏳ Pendiente

---

## Fase 7 — Frontend Web

**Estado:** ⏳ Pendiente

---

## Fase 8 — Documentación

**Estado:** ⏳ Pendiente

---

## Fase 9 — App Móvil

**Estado:** ⏳ Pendiente

---

## Fase 10 — Reglamento tarifario

**Estado:** ⏳ Pendiente

---

## Checklist final

- [x] Repositorio limpio
- [x] `docker compose config` sin errores
- [ ] `docker compose up -d` levanta todo
- [ ] Cluster Cassandra 2 nodos UP
- [ ] 120 000 medidores poblados
- [ ] 25 consultas funcionando
- [ ] Dashboard 3 roles funcional
- [ ] PDFs generados (5 categorías)
- [ ] Notificaciones funcionando
- [ ] App móvil funcional
- [ ] Reglamento tarifario implementado
- [ ] Informe técnico listo
- [ ] Glosario Cassandra completo
- [ ] CI/CD pasando

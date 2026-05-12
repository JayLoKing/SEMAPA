# 📊 Progreso del Proyecto SEMAPA

> Este archivo se actualiza al final de cada fase con: tareas completadas,
> archivos creados, comandos de verificación y resultados.

---

## Fase 0 — Repositorio y .gitignore

**Estado:** ⏳ Pendiente

**Tareas:**
- [ ] `git init` ejecutado
- [ ] `.gitignore` raíz creado
- [ ] `.dockerignore` en cada servicio
- [ ] `.env.example` con todas las variables
- [ ] `README.md` profesional
- [ ] `LICENSE` (MIT)
- [ ] `CONTRIBUTING.md`
- [ ] `.github/workflows/ci.yml`

**Verificación:**
```bash
git status
ls -la
```

---

## Fase 1 — Infraestructura y schema Cassandra

**Estado:** ⏳ Pendiente

**Tareas:**
- [ ] `docker-compose.yml` con cluster 2 nodos
- [ ] Schema CQL aplicado
- [ ] Healthchecks funcionando

**Verificación:**
```bash
docker compose up -d
docker exec semapa-cassandra-1 nodetool status
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; DESCRIBE TABLES;"
```

---

## Fase 2 — Seeder

**Estado:** ⏳ Pendiente

**Tareas:**
- [ ] CSVs derivados del Excel
- [ ] 85.000 personas
- [ ] 100.000 infraestructuras
- [ ] 120.000 medidores
- [ ] ~15M-21M lecturas

**Verificación:**
```bash
docker exec semapa-cassandra-1 cqlsh -e "SELECT COUNT(*) FROM semapa.medidores;"
```

**Tiempos de ejecución:**
- _Por completar_

---

## Fase 3 — Simulador + Ingestor

**Estado:** ⏳ Pendiente

---

## Fase 4 — Backend API

**Estado:** ⏳ Pendiente

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

- [ ] `docker compose up -d` levanta todo
- [ ] Cluster Cassandra 2 nodos UP
- [ ] 120.000 medidores poblados
- [ ] 25 consultas funcionando
- [ ] Dashboard 3 roles funcional
- [ ] PDFs generados (5 categorías)
- [ ] Notificaciones funcionando
- [ ] App móvil funcional
- [ ] Reglamento tarifario implementado
- [ ] Informe técnico listo (2 páginas)
- [ ] Glosario Cassandra completo
- [ ] CI/CD pasando

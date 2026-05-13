# SEMAPA — Seeder

Pobla masivamente Cassandra con catálogos, personas, infraestructuras, medidores y
lecturas históricas leyendo `Recursos Practica 5.xlsx`.

## Requisitos previos

- `docker compose up -d` (Cassandra cluster + redis + rabbitmq healthy)
- `cassandra-init` finalizado (schema aplicado)
- Archivo `Recursos Practica 5.xlsx` en la raíz del repo

## Uso

```bash
# 1) Catálogos + 85k personas + 100k+ infra + 120k medidores  (~5–15 min)
docker compose --profile tools run --rm seeder python -u seed.py

# 2) Lecturas históricas 2025-04-01..hoy  (~30–60 min, ~15M filas)
docker compose --profile tools run --rm seeder python -u seed_lecturas.py
```

## Variables de entorno

| Variable                    | Default               | Descripción                              |
|-----------------------------|-----------------------|------------------------------------------|
| `SEEDER_EXCEL`              | `/recursos/recursos.xlsx` | Ruta al Excel dentro del contenedor    |
| `SEEDS_DIR`                 | `/data/seeds`         | CSVs derivados                            |
| `SEED_CONCURRENCY`          | `120`                 | Concurrencia para inserciones             |
| `SEED_RNG`                  | `20250512`            | Semilla determinista                      |
| `LECTURAS_DESDE`            | `2025-04-01`          | Fecha inicial                             |
| `LECTURAS_HASTA`            | hoy                   | Fecha final                               |
| `LECTURAS_CONCURRENCY`      | `200`                 | Concurrencia para time-series             |
| `LECTURAS_BATCH`            | `5000`                | Filas por flush concurrente               |
| `LECTURAS_LIMITE_MEDIDORES` | `0`                   | Limita medidores (pruebas)                |

## Volúmenes esperados

| Entidad           | Cantidad     |
|-------------------|--------------|
| Personas          | 85 000       |
| Infraestructuras  | 100 000+     |
| Medidores         | 120 000      |
| Lecturas          | ~15M–21M     |

## Verificación

```bash
docker exec semapa-cassandra-1 cqlsh -e "
SELECT COUNT(*) FROM semapa.personas;
SELECT COUNT(*) FROM semapa.infraestructuras;
SELECT COUNT(*) FROM semapa.medidores;
"
```

## Optimización aplicada

- `cassandra-driver` con `TokenAwarePolicy(DCAwareRoundRobinPolicy)`
- Prepared statements compilados una vez
- `execute_concurrent_with_args(concurrency=120..200)`
- Inserción por lotes de 5 000 filas
- Lectura incremental acumulada (no se resetea) en time-series
- Particionamiento por `(medidor_id, anio_mes)` → particiones < 100 MB

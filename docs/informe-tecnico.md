# Informe Técnico — SEMAPA

> Práctica 5, Univalle Bolivia. Sistema distribuido de gestión inteligente
> de agua potable para 120.000 medidores IoT en Cochabamba. **Máximo 2 páginas.**

## 1. Arquitectura

Se implementó una arquitectura de **microservicios** con 4 capas: edge
(LoRaWAN simulado), ingesta (watchdog → Cassandra), servicios (API REST,
PDF, workers de notificación) y presentación (web React + móvil React
Native). Todo dockerizado con `docker compose`. Nginx actúa como reverse
proxy y balanceador entre dos réplicas de la API.

## 2. Justificación de Cassandra

Se eligió **Apache Cassandra 4.1** (wide-column store distribuido) sobre
alternativas relacionales por tres razones:

- **Volumen y velocidad de escritura**: 120k medidores × 3 lecturas/día
  generan ~21 millones de filas en mes y medio (~1 GB). Cassandra está
  optimizada para escrituras masivas en time-series.
- **Sin SPOF**: arquitectura masterless con replicación automática. Si un
  nodo cae, el otro sirve sin interrupción.
- **Escalabilidad horizontal lineal**: añadir un nodo solo requiere
  apuntar a los seeds existentes. El token ring se rebalancea solo.

### Diseño query-driven

Se modelaron tablas por consulta. La tabla grande `lecturas_por_medidor`
usa `PRIMARY KEY ((medidor_id, anio_mes), fecha_hora)`: la partition key
compuesta evita particiones gigantes (cada partición ≈ 90 filas/mes), y
el clustering `fecha_hora DESC` permite recuperar la última lectura en
O(1). Se desnormalizó `lecturas_por_zona_dia` para alimentar el dashboard
sin agregaciones costosas.

### Replication factor y consistencia

`SimpleStrategy` con **RF=2** en desarrollo (documentado
`NetworkTopologyStrategy` para producción multi-DC). Consistencia tunable
por consulta:
- Escrituras de facturación → `LOCAL_QUORUM` (durabilidad)
- Lecturas analíticas del dashboard → `ONE` (latencia baja)
- Inserciones de lecturas IoT → `ONE` (alto throughput, eventual)

## 3. Internals usados

**MemTable + CommitLog + SSTables + compactación**. Cada escritura va
sincrónicamente al CommitLog (durabilidad ante caída del nodo) y a la
MemTable (RAM). Cuando ésta supera su umbral, se flushea como SSTable
inmutable. Como SSTables no se modifican, borrados generan **tombstones**
que se limpian en compactación. Para la tabla de lecturas se configuró
**TimeWindowCompactionStrategy** (TWCS, ventanas de 7 días), ideal para
time-series: cada ventana se consolida en una sola SSTable, las lecturas
históricas son secuenciales en disco y la compactación es predecible. Se
activó **compresión LZ4** para reducir ~60% el espacio.

## 4. Distribución y escalabilidad

El cluster arranca con **2 nodos** (`cassandra-1` semilla,
`cassandra-2` se une vía gossip). Añadir un tercer nodo solo requiere
levantar otro contenedor con la misma `cluster_name` y `seeds`
apuntando a `cassandra-1`; el ring se rebalancea automáticamente. Se
documenta este procedimiento en `docs/arquitectura.md`.

## 5. Ingesta y deduplicación

El simulador genera archivos `.txt` por gateway con 0.5% de errores y
0.07% de duplicados (especificado por la práctica). El **ingestor** usa
`watchdog` para detectar archivos nuevos y **deduplica con Redis** (key
`mac:fecha_hora`, TTL 24h). Inserciones por lotes con
`execute_concurrent_with_args` y **prepared statements** compilados al
startup, alcanzando ~5.000 inserts/segundo en hardware modesto.

## 6. Facturación y reglamento

El servicio `TarifaService` implementa íntegramente el reglamento
tarifario vigente (PDF oficial SEMAPA): 9 categorías (R1-R4, C, CE, I,
P, S), cargo fijo de 12 m³/mes y 6 tramos progresivos. Aplica reglas
especiales por tipo de infraestructura (Art. 6, 14, 16, 17, etc.).
Los montos se calculan en USD usando cotización cacheada en Redis
(TTL 15 min) desde una API externa, con fallback documentado.

## 7. Stack y trade-offs

| Decisión | Justificación |
|---|---|
| FastAPI async | Throughput alto sin GIL, OpenAPI gratis |
| RabbitMQ vs Kafka | Volumen modesto, RabbitMQ es más simple |
| React + Vite | Build rápido, HMR, code-splitting nativo |
| Leaflet vs Mapbox | Open source, sin API key, suficiente |
| Expo en móvil | Build sin Xcode/Studio, deploy con QR |
| Multi-stage Docker | Imágenes finales delgadas (~80 MB API) |

## 8. Seguridad y operatividad

- JWT con expiración 12h, bcrypt cost 12 para passwords.
- **RBAC** con tres roles: Alcaldía (vista macro), Gerencia (operación),
  Contabilidad (facturación). Cada rol ve un dashboard diferente.
- Healthchecks en todos los servicios. Logs estructurados JSON con loguru.
- Rate limit básico (100 req/min/IP) via Redis.
- Dead-letter queue en RabbitMQ con 3 reintentos exponenciales.

## 9. Métricas alcanzadas

- 85.000 personas, 100.000 infraestructuras, 120.000 medidores
- ~15-21 millones de lecturas (~1 GB)
- 25 consultas estratégicas funcionales
- 3 PDFs por categoría (15 totales) generados y validados
- App móvil con geolocalización funcional sobre 5 medidores del campus

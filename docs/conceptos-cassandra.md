# Conceptos Cassandra — Glosario obligatorio para evaluación

Todo el equipo debe dominar estos conceptos. La práctica los evalúa
explícitamente.

## 1. Wide-column store

Modelo de datos donde cada fila puede tener un número distinto de columnas, y
las columnas se agrupan en "familias" (column families). Cassandra es
wide-column con sintaxis tipo SQL (CQL), pero internamente cada partición
puede contener millones de celdas indexadas por clustering key.

**Diferencia con columnar puro (ej. Parquet, ClickHouse):** los columnares
puros almacenan cada columna por separado para análisis OLAP. Cassandra
agrupa celdas dentro de cada partición y está optimizada para OLTP con alto
throughput de escritura.

## 2. Column families

Antiguo término para lo que hoy llamamos **tablas** en CQL. Cada column
family agrupa filas con un mismo schema lógico pero permite columnas
dinámicas. En CQL moderno, `CREATE TABLE` crea una column family.

## 3. Partition Key vs Clustering Columns

```cql
PRIMARY KEY ((medidor_id, anio_mes), fecha_hora)
```

- **Partition Key** `(medidor_id, anio_mes)`: define en qué **nodo** vive la
  fila. Se hashea con Murmur3 para encontrar el nodo dueño. Todas las filas
  con la misma partition key viven juntas.
- **Clustering Columns** `fecha_hora`: ordena las filas dentro de la
  partición. Permite queries con rangos eficientes (`WHERE fecha_hora > ?`).

**Regla de oro:** una partición NO debe superar los 100 MB ni los ~100k
celdas. Por eso particionamos lecturas por `(medidor_id, anio_mes)` y no
por `medidor_id` solo (saturaría la partición en pocos meses).

## 4. MemTable

Tabla en RAM donde se acumulan las escrituras recientes ordenadas por
clustering. Cuando alcanza un umbral (por defecto 25% de heap o tiempo), se
**flushea** a disco como una SSTable inmutable.

## 5. CommitLog

Archivo append-only en disco donde se escribe TODA mutación antes de la
MemTable. Garantiza durabilidad: si el nodo se cae, al reiniciar replay del
commit log reconstruye las MemTables perdidas. Es el equivalente al
**WAL** (Write-Ahead Log) de bases relacionales.

**Flujo de escritura:**
```
Cliente → CommitLog (disco) + MemTable (RAM)
         → ACK al cliente
         → eventualmente: flush a SSTable
```

## 6. SSTables (Sorted String Tables)

Archivos inmutables en disco resultado de flushear MemTables. Cada SSTable
contiene:
- Datos ordenados por partition key + clustering
- Bloom filter (para descartar rápido búsquedas)
- Índice de particiones
- Resumen (summary)

Como son inmutables, **actualizaciones y borrados se hacen escribiendo
tombstones**, no modificando archivos existentes.

## 7. Compactación

Proceso periódico que **fusiona varias SSTables en una nueva** para:
- Eliminar tombstones expirados
- Reducir lectura de muchos archivos pequeños
- Liberar espacio de filas obsoletas

**Estrategias:**
- **STCS (Size-Tiered):** default, agrupa SSTables de tamaño similar. Bueno
  para escritura intensiva.
- **LCS (Leveled):** SSTables en niveles, lecturas más predecibles. Bueno
  para read-heavy.
- **TWCS (Time-Window):** agrupa por ventana temporal. Ideal para
  **time-series**, que es nuestro caso en `lecturas_por_medidor`.

## 8. Gossip protocol

Protocolo peer-to-peer donde cada nodo intercambia metadata con otros 3
nodos cada segundo. Así el cluster mantiene visión consistente de qué
nodos están UP, DOWN o JOINING sin necesidad de coordinador central.

## 9. Anti-entropy repair

Operación que **compara hashes de datos entre réplicas** (Merkle trees)
para detectar y corregir divergencias. Se ejecuta con
`nodetool repair keyspace`. Recomendado correrlo regularmente
(ej. una vez por semana en prod) o tras agregar nodos.

## 10. Consistency levels

Nivel mínimo de réplicas que deben responder para considerar una operación
exitosa. **Configurables por consulta**.

| Level | Significado |
|---|---|
| `ANY` | Cualquier réplica (incluye hinted handoff). El más débil. |
| `ONE` | 1 réplica responde. Rápido, lecturas analíticas. |
| `QUORUM` | Mayoría: `(RF/2) + 1`. Balance C/A. |
| `LOCAL_QUORUM` | QUORUM dentro del DC local. Multi-DC. |
| `ALL` | Todas las réplicas. Más fuerte, más lento. |

**Tunable consistency:** `R + W > RF` garantiza consistencia fuerte.
- Con RF=2, W=QUORUM (2), R=ONE (1): 2+1 > 2 ✓
- Con RF=3, W=QUORUM (2), R=QUORUM (2): 2+2 > 3 ✓

En SEMAPA usamos:
- Escrituras de facturación: `LOCAL_QUORUM`
- Lecturas analíticas del dashboard: `ONE`
- Escrituras de lecturas IoT: `ONE` (alto throughput, eventual consistency)

## 11. Hinted handoff

Si un nodo está DOWN durante una escritura, otro nodo guarda un "hint"
(la mutación pendiente) y se la entrega cuando vuelva. Mejora disponibilidad
pero no garantiza consistencia si el nodo nunca regresa (los hints expiran).

## 12. Alta disponibilidad

Cassandra logra HA por diseño:
- **Sin SPOF**: arquitectura masterless (todos los nodos son iguales)
- **Replicación** automática según RF
- **Failover** transparente: si un nodo cae, otro toma el relevo
- **Datacenter awareness**: NetworkTopologyStrategy replica entre DCs

## 13. Escalabilidad horizontal

Añadir un nodo nuevo:
1. Configurar `cluster_name` igual y `seeds` apuntando a un nodo existente
2. Arranca → entra en estado JOINING
3. Recibe **token range** asignado, copia datos correspondientes
4. Cuando termina, pasa a estado UN (Up Normal)
5. Cluster ahora distribuye carga entre N nodos

**No hay re-sharding manual.** El token ring se rebalancea automáticamente.

## 14. Tombstones

Marcadores que indican "este registro fue borrado". Como SSTables son
inmutables, no se puede borrar físicamente hasta la próxima compactación.
**Riesgo:** demasiados tombstones en una partición degradan lecturas
(GC grace period default 10 días).

## 15. Read repair

Cuando una lectura detecta que las réplicas tienen versiones diferentes,
Cassandra **sincroniza la versión más reciente** automáticamente en
background. Trabaja en conjunto con anti-entropy repair.

## 16. Resumen para defensa oral

> **Cassandra es una base de datos NoSQL distribuida, wide-column, sin
> punto único de falla, optimizada para escrituras masivas y time-series.
> Cada escritura va al CommitLog (durabilidad) y a la MemTable (RAM);
> cuando ésta llena, se flushea como SSTable inmutable. La compactación
> consolida SSTables periódicamente. El modelo se diseña por consulta:
> elegimos partition key para distribución y clustering columns para
> ordenamiento. La consistencia es tunable por consulta, y la
> disponibilidad se logra por replicación y arquitectura masterless.**

## Comandos útiles

```bash
# Estado del cluster
docker exec semapa-cassandra-1 nodetool status

# Información de keyspace
docker exec semapa-cassandra-1 nodetool tablestats semapa.lecturas_por_medidor

# Forzar flush a SSTable
docker exec semapa-cassandra-1 nodetool flush semapa

# Compactación manual
docker exec semapa-cassandra-1 nodetool compact semapa

# Repair
docker exec semapa-cassandra-1 nodetool repair semapa
```

# Arquitectura SEMAPA

## Visión general

Sistema distribuido de microservicios para la gestión inteligente de agua
potable en Cochabamba. Capaz de ingestar lecturas de 120.000 medidores IoT,
almacenarlas en un cluster Cassandra distribuido, exponer dashboards
georreferenciados y emitir facturación automatizada.

## Diagrama de componentes

```mermaid
flowchart LR
    subgraph EDGE[Edge LoRaWAN]
        M[120k Medidores IoT]
        GW1[Gateway Teleferico]
        GW2[Gateway ParqueVial]
        GW3[Gateway ParqueLincon]
        GW4[Gateway Petrolera]
        GW5[Gateway 5]
        M --> GW1 & GW2 & GW3 & GW4 & GW5
    end

    SIM[Simulator]
    GW1 & GW2 & GW3 & GW4 & GW5 --> SIM
    SIM -->|.txt| FOLDER[/lora-data]
    FOLDER --> INGESTOR[Ingestor watchdog]
    INGESTOR --> REDIS[(Redis dedup)]
    INGESTOR --> CASS[(Cassandra 2 nodos)]

    subgraph BACKEND[Backend Microservicios]
        API1[FastAPI #1]
        API2[FastAPI #2]
        PDF[PDF Service]
        WE[Worker Email]
        WS[Worker SMS]
        WW[Worker WhatsApp]
    end

    API1 & API2 --> CASS
    API1 & API2 --> REDIS
    API1 & API2 --> RMQ[RabbitMQ]
    RMQ --> WE & WS & WW
    WE --> SMTP[Mailhog]
    PDF --> CASS

    subgraph CLIENT[Clientes]
        WEB[React Web]
        MOB[Mobile Expo]
    end

    NGINX[Nginx LB]
    WEB & MOB --> NGINX
    NGINX --> API1 & API2 & PDF
```

## Capas

### Capa 1 — Edge LoRaWAN
- 120.000 medidores IoT distribuidos en 100k infraestructuras
- 5 gateways LoRaWAN (Teleferico, ParqueVial, ParqueLincon, Petrolera + 1)
- Comunicación simulada por el servicio `simulator`

### Capa 2 — Ingesta
- `simulator` genera archivos `.txt` por medidor en `/lora-data/{gateway}/`
- `ingestor` con `watchdog` detecta archivos nuevos
- Deduplicación en Redis (key `mac:fecha_hora`, TTL 24h)
- Inserción batch async a Cassandra usando prepared statements

### Capa 3 — Datos (Cassandra)
- Cluster de 2 nodos (escalable horizontalmente)
- Replication factor 2, SimpleStrategy (NetworkTopologyStrategy en prod)
- Particionamiento por `(medidor_id, anio_mes)` en lecturas
- Denormalización: `lecturas_por_zona_dia` para queries del dashboard
- Compresión LZ4 + TimeWindowCompactionStrategy en la tabla grande

### Capa 4 — Servicios
- **API REST** FastAPI (2 réplicas) detrás de Nginx con least-conn
- **PDF Service** independiente (ReportLab)
- **Workers** de notificación: 3 servicios separados consumiendo RabbitMQ
- **Cache** Redis para cotización USD y resultados pesados

### Capa 5 — Presentación
- **Web** React + Vite, 3 roles diferenciados
- **Mobile** React Native + Expo para lectura manual con GPS

## Flujo de datos: lectura → factura → recibo

1. Simulador genera archivo `.txt` en `/lora-data/{gateway}/{ts}/{mac}.txt`
2. Ingestor detecta archivo → valida → dedup → inserta en Cassandra
3. Job programado (mensual) recorre `lecturas_por_medidor` y calcula consumo
   total por medidor
4. `TarifaService` aplica reglamento (PDF) y obtiene monto en USD
5. `factura_service` escribe en `facturas` y `facturas_por_periodo`
6. Usuario en dashboard pulsa "Enviar recibo" → POST `/api/v1/notify`
7. API publica mensaje en RabbitMQ exchange `semapa.notifications`
8. Workers consumen: email vía SMTP a Mailhog (dev), SMS y WhatsApp mock
9. PDF service genera los 2 formatos a demanda para el adjunto del email

## Trade-offs

| Decisión | Pros | Contras |
|---|---|---|
| Cassandra wide-column | Escala horizontal, time-series, alta disponibilidad | Sin JOINs, modelar por consulta |
| Denormalización | Lecturas rápidas en dashboard | Mantener consistencia en escritura |
| RabbitMQ vs Kafka | Más simple, suficiente para el volumen | Menos throughput que Kafka |
| 2 nodos Cassandra | Suficiente para demo, RF=2 | En prod se recomiendan 3+ por DC |
| JWT stateless | Escalable, sin sesión central | Revocación requiere blacklist |
| Mailhog dev | Captura local sin enviar | No es producción |

## Escalado horizontal

Para agregar un tercer nodo Cassandra:

```bash
# 1. Añadir servicio cassandra-3 al docker-compose con seeds=cassandra-1
# 2. Levantar: docker compose up -d cassandra-3
# 3. Esperar a que esté UN: docker exec semapa-cassandra-1 nodetool status
# 4. Repair: docker exec semapa-cassandra-1 nodetool repair semapa
# 5. Actualizar CASSANDRA_HOSTS en .env
```

Para escalar la API: añadir `api-3`, `api-4` al `docker-compose.yml` y al
`upstream api_backend` de Nginx.

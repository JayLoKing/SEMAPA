# SEMAPA API — Referencia rápida

Base URL local: `http://localhost/api/v1` (vía Nginx) o `http://localhost:8000/api/v1` (directo).
Swagger UI: `http://localhost/api/v1/docs`.

## Auth

| Método | Path                | Descripción                                |
|--------|---------------------|--------------------------------------------|
| POST   | `/auth/login`       | `{username, password}` → JWT + rol         |
| GET    | `/auth/me`          | Datos del usuario actual (requiere bearer) |
| POST   | `/auth/logout`      | Logout (stateless en el cliente)           |

Usuarios por defecto (creados por el seeder):

| Username    | Password         | Rol           |
|-------------|------------------|---------------|
| alcaldia    | `Alcaldia2025!`  | ALCALDIA      |
| gerencia    | `Gerencia2025!`  | GERENCIA      |
| contabilidad| `Contab2025!`    | CONTABILIDAD  |

## Dashboard

| Método | Path                                                                       |
|--------|----------------------------------------------------------------------------|
| GET    | `/dashboard/kpis?sub_alcaldia=&distrito=&zona=&desde=&hasta=`              |

KPIs varían por rol (Alcaldía / Gerencia / Contabilidad).

## Consultas analíticas (25 + extras)

Todas requieren JWT. Resultados cacheados en Redis (TTL 60–600s).

| Path                                              | Descripción                                   |
|---------------------------------------------------|-----------------------------------------------|
| `/consultas/consumo-promedio-distrito?rango_horas=8` | Promedio por distrito en bloque horario     |
| `/consultas/comparativa-semanas?distritos=1,2,3`  | Comparativa semanal                           |
| `/consultas/consumos-excesivos?umbral_pct=0.3`    | Medidores que exceden tope                    |
| `/consultas/medidores-activos`                    | Conteo por estado                             |
| `/consultas/medidores-fuera-servicio`             | Lista de medidores FUERA_SERVICIO             |
| `/consultas/modelos-mas-fallas`                   | Tasa de falla por modelo                      |
| `/consultas/consumo-por-tarifa-distrito`          | Cruce categoría × distrito                    |
| `/consultas/zonas-anomalas`                       | Top 20 zonas con mayor consumo                |
| `/consultas/lecturas-fallidas-mes`                | (placeholder ETL)                             |
| `/consultas/medidores-mas-4-anios`                | Antiguos para renovación                      |
| `/consultas/per-capita-residencial`               | Consumo por habitante                         |
| `/consultas/top3-consumidores-distrito`           | Top 3 por distrito                            |
| `/consultas/zonas-renovacion`                     | Zonas con alta tasa de fuera de servicio      |
| `/consultas/zonas-errores-por-distrito?distrito=1`| Zonas con errores en distrito X               |
| `/consultas/cobertura-antenas`                    | Medidores por gateway                         |
| `/consultas/proyeccion-demanda-5anios`            | Regresión lineal mensual                      |
| `/consultas/impacto-cambio-tarifa?desde=P&hacia=R4`| Simulación de migración tarifaria             |
| `/consultas/medidores-sin-reporte?horas=72`       | Sin reporte > N horas                         |
| `/consultas/proyeccion-ingresos-mes`              | Ingresos USD aproximados                      |
| `/consultas/consumo-minimo-residencial`           | Mínimo del reglamento                         |
| `/consultas/ingresos-pies3`                       | Consumo convertido a pies cúbicos             |
| `/consultas/distribucion-categorias`              | Histograma de medidores                       |
| `/consultas/horas-pico`                           | Consumo por hora del día                      |
| `/consultas/medidores-por-modelo`                 | Conteo por modelo                             |
| `/consultas/resumen-cobertura-poblacional`        | Medidores por 1 000 habitantes                |

## Facturación

| Método | Path                                                    | Descripción                  |
|--------|---------------------------------------------------------|------------------------------|
| GET    | `/facturas/{numero_contrato}/{periodo}`                 | Obtener factura              |
| POST   | `/facturas/generar?periodo=YYYY-MM&limite=100`          | Generar lote (CONTABILIDAD)  |
| GET    | `http://localhost/pdf?numero_contrato=&periodo=&formato=medicarta\|rollo` | PDF |
| POST   | `http://localhost/pdf/batch`                            | ZIP con varios PDFs          |

## Notificaciones

| Método | Path           | Body                                                           |
|--------|----------------|----------------------------------------------------------------|
| POST   | `/notify`      | `{formato: email\|sms\|whatsapp, identificador, valor, periodo}`|

Publica al exchange topic `semapa.notifications` con routing key `notify.{formato}`.

## Otros

| Método | Path                                  | Descripción                                |
|--------|---------------------------------------|--------------------------------------------|
| GET    | `/usd/cotizacion`                     | Cotización USD→BOB (cache 15 min Redis)    |
| GET    | `/buscar?q=...`                       | Búsqueda unificada                         |
| POST   | `/lecturas/manual`                    | Lectura manual (app móvil)                 |
| GET    | `/health`                             | Healthcheck                                |

## Códigos HTTP

| Código | Significado                              |
|--------|------------------------------------------|
| 200    | OK                                       |
| 401    | Token faltante / inválido / expirado     |
| 403    | Rol no autorizado                        |
| 404    | Recurso no encontrado                    |
| 429    | Rate limit excedido (>200 req/min/IP)    |
| 503    | Broker / Cassandra no disponible         |

## Convenciones

- Todas las fechas en `ISO 8601` (`YYYY-MM-DD` o `YYYY-MM-DDTHH:MM:SS`).
- Montos en `string` con punto decimal (`"123.45"`).
- IDs UUID v4 serializados como string.
- Paginación: `?limit=&offset=` (default 50, max 500).

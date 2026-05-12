<div align="center">

# 💧 SEMAPA — Gestión Inteligente de Agua Potable

**Sistema distribuido para la empresa municipal de agua potable de Cochabamba**

[![Cassandra](https://img.shields.io/badge/Cassandra-4.1-1287B1?logo=apachecassandra)](https://cassandra.apache.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Práctica 5 — Univalle Bolivia

</div>

---

## 📋 Tabla de Contenido

- [Descripción](#-descripción)
- [Arquitectura](#-arquitectura)
- [Stack Tecnológico](#-stack-tecnológico)
- [Requisitos](#-requisitos)
- [Cómo levantar el sistema](#-cómo-levantar-el-sistema)
- [Poblado de datos](#-poblado-de-datos)
- [Credenciales](#-credenciales-por-defecto)
- [Endpoints principales](#-endpoints-principales)
- [Puertos expuestos](#-puertos-expuestos)
- [Estructura del repo](#-estructura-del-repo)
- [Equipo](#-equipo)

---

## 🎯 Descripción

SEMAPA gestiona **120.000 medidores IoT** distribuidos en **100.000 infraestructuras** a lo largo de los **14 distritos** de Cochabamba. El sistema:

- Recibe lecturas de medidores vía red **LoRaWAN** simulada (5 gateways).
- Almacena ~21 millones de lecturas en un **cluster Cassandra distribuido**.
- Visualiza consumo en un **dashboard georreferenciado** con 3 niveles de acceso (Alcaldía, Gerencia, Contabilidad).
- Genera **pre-facturación automática** con cálculo según el reglamento tarifario vigente.
- Emite recibos en **PDF (rollo térmico y media carta)**.
- Despacha notificaciones por **email, SMS y WhatsApp** vía RabbitMQ.
- Incluye una **app móvil** para lectura manual con geolocalización.

---

## 🏗️ Arquitectura

```
                ┌──────────────┐   ┌──────────────┐
   Medidores ──▶│ LoRaWAN GWs  │──▶│  Simulator   │──▶ /lora-data/*.txt
   IoT 120k     └──────────────┘   └──────────────┘            │
                                                               ▼
                                                       ┌──────────────┐
                                                       │   Ingestor   │
                                                       │   (watcher)  │
                                                       └──────┬───────┘
                                                              │
                                                              ▼
                                          ┌─────────────────────────────────┐
                                          │  Cassandra Cluster (2 nodos)    │
                                          │  RF=2, escalado horizontal      │
                                          └─────────────────────────────────┘
                                                              ▲
                                          ┌───────────────────┴────────────┐
                                          │                                │
                                  ┌───────┴───────┐               ┌────────┴───────┐
                                  │  FastAPI x2   │               │  PDF Service   │
                                  │   (Nginx LB)  │               │   ReportLab    │
                                  └───────┬───────┘               └────────────────┘
                                          │
                          ┌───────────────┼────────────────┐
                          ▼               ▼                ▼
                  ┌────────────┐  ┌────────────┐  ┌─────────────────┐
                  │ React Web  │  │  RN Móvil  │  │ RabbitMQ        │
                  │ 3 roles    │  │  + GPS     │  │ Email/SMS/WApp  │
                  └────────────┘  └────────────┘  └─────────────────┘
```

Documentación completa en [`docs/arquitectura.md`](docs/arquitectura.md).

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|---|---|
| **Base de datos** | Apache Cassandra 4.1 (cluster 2 nodos, RF=2) |
| **Backend** | Python 3.11 + FastAPI + cassandra-driver |
| **Cache** | Redis 7 |
| **Broker** | RabbitMQ 3.13 |
| **PDFs** | ReportLab + Jinja2 |
| **Frontend Web** | React 18 + Vite + TypeScript + TailwindCSS |
| **Mapas** | Leaflet + react-leaflet + heatmap + clustering |
| **Gráficos** | Recharts + Chart.js |
| **App Móvil** | React Native + Expo + expo-location |
| **Reverse Proxy** | Nginx (load balancer) |
| **SMTP dev** | Mailhog |
| **Orquestación** | Docker Compose |

---

## ⚙️ Requisitos

- Docker ≥ 24.0
- Docker Compose ≥ 2.20
- 8 GB RAM mínimo (recomendado 16 GB para el seed completo)
- 20 GB libres en disco

---

## 🚀 Cómo levantar el sistema

```bash
# 1. Clonar el repositorio
git clone <tu-repo-url>
cd semapa

# 2. Copiar variables de entorno
cp .env.example .env
# Edita .env con tus valores

# 3. Levantar todo el stack
docker compose up -d

# 4. Verificar que el cluster Cassandra está UP
docker exec semapa-cassandra-1 nodetool status
# Debe mostrar 2 nodos con status UN

# 5. Verificar que el schema fue aplicado
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; DESCRIBE TABLES;"
```

---

## 🌱 Poblado de datos

```bash
# Poblar catálogos, personas, infraestructuras y medidores (rápido, ~5 min)
docker compose run --rm seeder python seed.py

# Poblar lecturas históricas (lento, ~30-60 min)
docker compose run --rm seeder python seed_lecturas.py
```

**Volumen esperado:**
- 85.000 personas
- 100.000 infraestructuras
- 120.000 medidores
- ~15M - 21M lecturas (~1 GB)

---

## 🔑 Credenciales por defecto

| Rol | Usuario | Contraseña |
|---|---|---|
| Alcaldía | `alcaldia` | `Alcaldia2025!` |
| Gerencia SEMAPA | `gerencia` | `Gerencia2025!` |
| Contabilidad SEMAPA | `contabilidad` | `Contab2025!` |

**⚠️ Cambiar en producción.**

---

## 🌐 Endpoints principales

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Login y obtención de JWT |
| `GET` | `/api/v1/dashboard/kpis` | KPIs del dashboard (filtrable) |
| `GET` | `/api/v1/consultas/...` | 25 consultas estratégicas |
| `GET` | `/api/v1/buscar?q=...` | Buscador (contrato/MAC/cliente) |
| `POST` | `/api/v1/facturas/generar` | Generar facturas del periodo |
| `GET` | `/api/v1/facturas/{contrato}/{periodo}/pdf` | Descargar PDF |
| `POST` | `/api/v1/notify` | Enviar recibo por email/SMS/WhatsApp |
| `POST` | `/api/v1/lecturas/manual` | Registro manual (app móvil) |

Documentación interactiva: **http://localhost/api/v1/docs**

---

## 🔌 Puertos expuestos

| Servicio | Puerto |
|---|---|
| Frontend Web | `http://localhost` |
| API (Swagger) | `http://localhost/api/v1/docs` |
| Cassandra (CQL) | `localhost:9042` |
| Redis | `localhost:6379` |
| RabbitMQ AMQP | `localhost:5672` |
| RabbitMQ UI | `http://localhost:15672` |
| Mailhog UI | `http://localhost:8025` |

---

## 📁 Estructura del repo

```
semapa/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── docs/                    # Documentación técnica
├── infra/                   # Configuración de infraestructura
│   ├── cassandra/init/      # Schemas CQL
│   ├── nginx/               # Reverse proxy config
│   └── rabbitmq/            # Definitions y config
├── data/seeds/              # CSVs derivados del Excel
├── lora-data/               # Carpeta watch del ingestor
├── services/                # Microservicios
│   ├── api/                 # Backend FastAPI
│   ├── ingestor/            # Watcher LoRaWAN
│   ├── simulator/           # Generador de archivos
│   ├── seeder/              # Poblado masivo
│   ├── pdf-service/         # Generación de PDFs
│   ├── worker-email/
│   ├── worker-sms/
│   └── worker-whatsapp/
├── web/                     # Frontend React
└── mobile/                  # App móvil Expo
```

---

## 📚 Documentación adicional

- [Arquitectura detallada](docs/arquitectura.md)
- [Informe técnico (2 páginas)](docs/informe-tecnico.md)
- [Conceptos Cassandra](docs/conceptos-cassandra.md)
- [Reglamento tarifario](docs/reglamento-tarifario.md)
- [API completa](docs/api.md)

---

## 👥 Equipo

- _Equipo Univalle — Práctica 5_

---

## 📄 Licencia

MIT — ver [LICENSE](LICENSE).

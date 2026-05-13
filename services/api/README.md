# SEMAPA — API (FastAPI)

Backend principal del sistema. Expone endpoints REST para autenticación, 
consultas, dashboard, facturación y notificaciones.

## Estructura

```
app/
├── main.py              # Entry point FastAPI, lifespan
├── core/
│   ├── config.py        # Pydantic Settings
│   ├── security.py      # JWT, bcrypt, RBAC
│   ├── cassandra_client.py  # Cluster singleton + prepared statements
│   ├── redis_client.py
│   └── rabbitmq_client.py
├── routers/
│   ├── auth.py
│   ├── medidores.py
│   ├── lecturas.py
│   ├── facturas.py
│   ├── consultas.py     # Las 25 consultas estratégicas
│   ├── dashboard.py     # Endpoints por rol
│   ├── notify.py
│   ├── usd.py
│   └── buscar.py
├── services/
│   ├── tarifa_service.py    # Aplica reglamento del PDF
│   ├── factura_service.py
│   ├── usd_service.py       # Cache Redis 15 min
│   └── notification_service.py
└── models/              # Pydantic schemas
```

## Variables de entorno

Ver `.env.example` en la raíz del proyecto.

## Desarrollo local

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Docker

```bash
docker compose up api-1 api-2
```

## Tests

```bash
pytest tests/ -v
```

## Endpoints

Swagger UI: http://localhost/api/v1/docs

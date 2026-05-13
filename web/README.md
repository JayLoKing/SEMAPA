# SEMAPA — Frontend Web

Aplicación web React + Vite + TypeScript + TailwindCSS con 3 dashboards
diferenciados por rol (Alcaldía, Gerencia, Contabilidad).

## Stack

- React 18 + Vite + TypeScript
- TailwindCSS 3
- react-leaflet + heatmap + clustering (mapa de medidores)
- Recharts + Chart.js (visualizaciones)
- Zustand (estado global) + TanStack Query (fetch)
- React Router v6 con guards por rol

## Desarrollo

```bash
npm install
npm run dev
```

Abre `http://localhost:5173`.

## Build

```bash
npm run build
```

## Docker

```bash
docker compose up web
```

Servido en `http://localhost` a través de Nginx.

## Estructura sugerida

```
src/
├── api/              # axios client + endpoints tipados
├── auth/             # login, JWT, guards
├── components/       # UI compartido
├── pages/
│   ├── Login.tsx
│   ├── DashboardAlcaldia.tsx
│   ├── DashboardGerencia.tsx
│   ├── DashboardContabilidad.tsx
│   ├── Mapa.tsx
│   ├── Facturacion.tsx
│   └── Consultas.tsx
├── store/            # Zustand
├── hooks/
├── utils/
└── App.tsx
```

## Variables de entorno

`VITE_API_URL=http://localhost/api/v1`

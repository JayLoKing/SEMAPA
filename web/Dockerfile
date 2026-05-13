# ============================================================================
# SEMAPA - Frontend Web (React + Vite + TypeScript)
# Multi-stage: build con node, sirve con nginx (alpine, ~25 MB final)
# ============================================================================

# ----- Stage 1: build -----
FROM node:20-alpine AS builder

WORKDIR /app

# Cachea node_modules: copia primero los manifests
COPY package*.json ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

# Copia el código y construye
COPY . .

ARG VITE_API_URL=http://localhost/api/v1
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# ----- Stage 2: serve con nginx -----
FROM nginx:alpine AS runtime

# Copia el bundle generado
COPY --from=builder /app/dist /usr/share/nginx/html

# Configuración SPA (fallback a index.html en rutas client-side)
RUN echo 'server { \
    listen 80; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    gzip on; \
    gzip_types text/plain text/css application/json application/javascript text/javascript application/xml image/svg+xml; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf)$ { \
        expires 1y; \
        add_header Cache-Control "public, immutable"; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget --spider -q http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

#!/usr/bin/env bash
# ============================================================================
# SEMAPA - Bootstrap
# Inicializa el proyecto desde cero: .env, build, up, seed
# Uso: ./scripts/bootstrap.sh
# ============================================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

step() { echo -e "\n${BLUE}═══ $1 ═══${NC}"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}!${NC} $1"; }

# Verificar prerequisitos
step "Verificando prerequisitos"
command -v docker >/dev/null || fail "Docker no instalado"
command -v docker compose >/dev/null 2>&1 || docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 no instalado"
ok "Docker y Docker Compose presentes"

# .env
step "Configurando .env"
if [[ -f .env ]]; then
    warn ".env ya existe, no se sobrescribe"
else
    cp .env.example .env
    ok ".env creado desde .env.example"
    warn "Recuerda revisar las variables en .env (especialmente JWT_SECRET)"
fi

# Build de imágenes
step "Construyendo imágenes Docker (esto tarda en la primera vez)"
docker compose build --parallel
ok "Imágenes construidas"

# Up
step "Levantando servicios"
docker compose up -d
ok "Servicios iniciados"

# Esperar cluster Cassandra
step "Esperando a que el cluster Cassandra esté listo (puede tardar ~90s)"
for i in {1..30}; do
    UN=$(docker exec semapa-cassandra-1 nodetool status 2>/dev/null | grep -c "^UN " || echo 0)
    if [[ "$UN" -eq 2 ]]; then
        ok "Cluster con 2 nodos UN"
        break
    fi
    echo -n "."
    sleep 5
done
[[ "$UN" -eq 2 ]] || fail "Cluster no alcanzó 2 nodos UN en 150s"

# Verificar schema
step "Verificando schema"
sleep 10
TABLES=$(docker exec semapa-cassandra-1 cqlsh -e "USE semapa; DESCRIBE TABLES;" 2>/dev/null | tr -s ' ' '\n' | grep -v '^$' | wc -l)
[[ "$TABLES" -ge 16 ]] && ok "Schema con $TABLES tablas" || warn "Solo $TABLES tablas (puede requerir reintentar 'cassandra-init')"

# Resumen
step "Bootstrap completado"
echo ""
echo "Servicios disponibles:"
echo "  • Web:           http://localhost"
echo "  • API Swagger:   http://localhost/api/v1/docs"
echo "  • RabbitMQ UI:   http://localhost:15672 (semapa / semapa)"
echo "  • Mailhog UI:    http://localhost:8025"
echo "  • Cassandra:     localhost:9042"
echo ""
echo "Próximos pasos:"
echo "  1. Poblar la base:        make seed"
echo "  2. Poblar lecturas:       make seed-lecturas"
echo "  3. Smoke test:            make smoke"
echo ""

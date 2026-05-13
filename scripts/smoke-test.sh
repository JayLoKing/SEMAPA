#!/usr/bin/env bash
# ============================================================================
# SEMAPA - Smoke Test
# Valida que el sistema está correctamente desplegado tras cada fase
# Uso: ./scripts/smoke-test.sh [fase]
#      fases: 1 (infra), 2 (seed), 3 (ingestor), 4 (api), 5 (pdf), 6 (notify), all
# ============================================================================
set -e

FASE=${1:-all}
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
info() { echo -e "${BLUE}▶${NC} $1"; }

# ============================================================================
# FASE 1 — Infraestructura
# ============================================================================
test_fase_1() {
    info "Fase 1: Infraestructura"

    info "Verificando contenedores activos..."
    docker compose ps --services --filter "status=running" | grep -q "cassandra-1" \
        && ok "cassandra-1 corriendo" \
        || fail "cassandra-1 no está corriendo"
    docker compose ps --services --filter "status=running" | grep -q "cassandra-2" \
        && ok "cassandra-2 corriendo" \
        || fail "cassandra-2 no está corriendo"
    docker compose ps --services --filter "status=running" | grep -q "redis" \
        && ok "redis corriendo" \
        || fail "redis no está corriendo"
    docker compose ps --services --filter "status=running" | grep -q "rabbitmq" \
        && ok "rabbitmq corriendo" \
        || fail "rabbitmq no está corriendo"

    info "Verificando cluster Cassandra (2 nodos UN)..."
    UN_COUNT=$(docker exec semapa-cassandra-1 nodetool status 2>/dev/null | grep -c "^UN " || echo 0)
    [[ "$UN_COUNT" -eq 2 ]] \
        && ok "Cluster Cassandra: 2 nodos Up Normal" \
        || fail "Cluster esperado 2 UN, encontrados: $UN_COUNT"

    info "Verificando schema..."
    TABLES=$(docker exec semapa-cassandra-1 cqlsh -e "USE semapa; DESCRIBE TABLES;" 2>/dev/null | tr -s ' ' '\n' | grep -v '^$' | wc -l)
    [[ "$TABLES" -ge 16 ]] \
        && ok "Schema con $TABLES tablas" \
        || fail "Esperado >= 16 tablas, encontradas: $TABLES"

    info "Verificando RabbitMQ UI..."
    curl -sf -u semapa:semapa http://localhost:15672/api/overview > /dev/null \
        && ok "RabbitMQ Management UI accesible" \
        || warn "RabbitMQ UI no responde (puede tardar)"

    info "Verificando Mailhog UI..."
    curl -sf http://localhost:8025/api/v2/messages > /dev/null \
        && ok "Mailhog UI accesible" \
        || warn "Mailhog UI no responde"
}

# ============================================================================
# FASE 2 — Seed
# ============================================================================
test_fase_2() {
    info "Fase 2: Poblado de datos"

    PERSONAS=$(docker exec semapa-cassandra-1 cqlsh -e "SELECT COUNT(*) FROM semapa.personas;" 2>/dev/null | grep -oE '[0-9]+' | tail -1)
    INFRA=$(docker exec semapa-cassandra-1 cqlsh -e "SELECT COUNT(*) FROM semapa.infraestructuras;" 2>/dev/null | grep -oE '[0-9]+' | tail -1)
    MED=$(docker exec semapa-cassandra-1 cqlsh -e "SELECT COUNT(*) FROM semapa.medidores;" 2>/dev/null | grep -oE '[0-9]+' | tail -1)

    [[ "$PERSONAS" -ge 80000 ]] \
        && ok "Personas: $PERSONAS (esperado ≥ 80.000)" \
        || warn "Personas: $PERSONAS"
    [[ "$INFRA" -ge 99000 ]] \
        && ok "Infraestructuras: $INFRA (esperado ≥ 99.000)" \
        || warn "Infraestructuras: $INFRA"
    [[ "$MED" -ge 119000 ]] \
        && ok "Medidores: $MED (esperado ≥ 119.000)" \
        || warn "Medidores: $MED"

    info "Verificando usuarios del sistema..."
    USERS=$(docker exec semapa-cassandra-1 cqlsh -e "SELECT username,rol FROM semapa.usuarios_sistema;" 2>/dev/null | grep -cE 'alcaldia|gerencia|contabilidad' || echo 0)
    [[ "$USERS" -ge 3 ]] \
        && ok "3 usuarios del sistema creados" \
        || warn "Solo $USERS usuarios encontrados"
}

# ============================================================================
# FASE 3 — Ingestor
# ============================================================================
test_fase_3() {
    info "Fase 3: Simulador + Ingestor"

    docker compose ps --services --filter "status=running" | grep -q "ingestor" \
        && ok "Ingestor corriendo" \
        || warn "Ingestor no corriendo"
    docker compose ps --services --filter "status=running" | grep -q "simulator" \
        && ok "Simulator corriendo" \
        || warn "Simulator no corriendo"

    RAW=$(docker exec semapa-cassandra-1 cqlsh -e "SELECT COUNT(*) FROM semapa.lecturas_raw;" 2>/dev/null | grep -oE '[0-9]+' | tail -1)
    [[ "$RAW" -gt 0 ]] \
        && ok "lecturas_raw: $RAW registros" \
        || warn "No hay lecturas_raw aún"
}

# ============================================================================
# FASE 4 — API
# ============================================================================
test_fase_4() {
    info "Fase 4: Backend API"

    curl -sf http://localhost/healthz > /dev/null \
        && ok "Nginx healthz responde" \
        || fail "Nginx no responde en /healthz"

    HEALTH=$(curl -sf http://localhost/api/v1/health 2>/dev/null || echo "")
    echo "$HEALTH" | grep -q "ok" \
        && ok "API /health responde" \
        || warn "API /health no responde aún"

    info "Probando login..."
    TOKEN=$(curl -sf -X POST http://localhost/api/v1/auth/login \
        -H "Content-Type: application/json" \
        -d '{"username":"alcaldia","password":"Alcaldia2025!"}' \
        2>/dev/null | grep -oE '"access_token":"[^"]+"' | cut -d'"' -f4)
    [[ -n "$TOKEN" ]] \
        && ok "Login funciona (token recibido)" \
        || warn "Login no responde token aún"
}

# ============================================================================
# FASE 5 — PDF
# ============================================================================
test_fase_5() {
    info "Fase 5: PDF Service"

    docker compose ps --services --filter "status=running" | grep -q "pdf-service" \
        && ok "PDF service corriendo" \
        || warn "PDF service no corriendo"
}

# ============================================================================
# FASE 6 — Notify
# ============================================================================
test_fase_6() {
    info "Fase 6: Workers de notificación"

    for w in worker-email worker-sms worker-whatsapp; do
        docker compose ps --services --filter "status=running" | grep -q "$w" \
            && ok "$w corriendo" \
            || warn "$w no corriendo"
    done
}

# ============================================================================
# Main
# ============================================================================
echo ""
echo "============================================="
echo "  SEMAPA — Smoke Test (fase: $FASE)"
echo "============================================="
echo ""

case "$FASE" in
    1) test_fase_1 ;;
    2) test_fase_2 ;;
    3) test_fase_3 ;;
    4) test_fase_4 ;;
    5) test_fase_5 ;;
    6) test_fase_6 ;;
    all)
        test_fase_1
        echo ""
        test_fase_2 || true
        echo ""
        test_fase_3 || true
        echo ""
        test_fase_4 || true
        echo ""
        test_fase_5 || true
        echo ""
        test_fase_6 || true
        ;;
    *) echo "Fase desconocida: $FASE"; exit 1 ;;
esac

echo ""
echo -e "${GREEN}Smoke test completado.${NC}"

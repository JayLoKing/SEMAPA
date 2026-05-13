# ============================================================================
# SEMAPA - Makefile
# Comandos comunes para desarrollo y operación
# ============================================================================

.PHONY: help up down restart logs ps clean \
        cassandra-status cassandra-schema cassandra-cqlsh \
        seed seed-lecturas \
        test test-api smoke smoke-1 smoke-2 smoke-3 smoke-4 \
        rabbitmq-ui mailhog \
        build pull lint format

# ===== Help =====
help: ## Muestra esta ayuda
	@echo "SEMAPA - Comandos disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'

# ===== Infraestructura =====
up: ## Levanta todo el stack
	docker compose up -d
	@echo "Esperando cluster Cassandra..."
	@sleep 30
	@docker exec semapa-cassandra-1 nodetool status 2>/dev/null || echo "Cluster aún inicializando, ejecuta 'make cassandra-status' en 30s"

down: ## Detiene todo el stack
	docker compose down

restart: ## Reinicia todo
	docker compose restart

logs: ## Muestra logs de todos los servicios
	docker compose logs -f --tail=100

ps: ## Lista contenedores
	docker compose ps

clean: ## Limpia contenedores y volúmenes (¡cuidado!)
	docker compose down -v
	@echo "Volúmenes eliminados."

build: ## Construye todas las imágenes
	docker compose build --parallel

pull: ## Descarga imágenes base
	docker compose pull

# ===== Cassandra =====
cassandra-status: ## Muestra estado del cluster
	docker exec semapa-cassandra-1 nodetool status

cassandra-schema: ## Lista las tablas del keyspace semapa
	docker exec semapa-cassandra-1 cqlsh -e "USE semapa; DESCRIBE TABLES;"

cassandra-cqlsh: ## Abre shell interactivo cqlsh
	docker exec -it semapa-cassandra-1 cqlsh

cassandra-counts: ## Cuenta registros en tablas principales
	@docker exec semapa-cassandra-1 cqlsh -e "\
		USE semapa; \
		SELECT 'personas' AS tabla, COUNT(*) FROM personas; \
		SELECT 'infraestructuras' AS tabla, COUNT(*) FROM infraestructuras; \
		SELECT 'medidores' AS tabla, COUNT(*) FROM medidores;"

# ===== Seed =====
seed: ## Pobla catálogos, personas, infraestructuras, medidores
	docker compose run --rm seeder python seed.py

seed-lecturas: ## Pobla las ~15M lecturas históricas (lento)
	docker compose run --rm seeder python seed_lecturas.py

# ===== Tests =====
test: test-api ## Corre todos los tests

test-api: ## Tests del backend API
	docker compose exec api-1 pytest -v

smoke: ## Smoke test completo
	./scripts/smoke-test.sh all

smoke-1: ## Smoke test Fase 1 (infra)
	./scripts/smoke-test.sh 1

smoke-2: ## Smoke test Fase 2 (seed)
	./scripts/smoke-test.sh 2

smoke-3: ## Smoke test Fase 3 (ingestor)
	./scripts/smoke-test.sh 3

smoke-4: ## Smoke test Fase 4 (api)
	./scripts/smoke-test.sh 4

# ===== Acceso rápido a UIs =====
rabbitmq-ui: ## Abre RabbitMQ Management UI
	@echo "RabbitMQ UI: http://localhost:15672 (usuario: semapa / pwd: semapa)"

mailhog: ## Abre Mailhog UI
	@echo "Mailhog UI: http://localhost:8025"

api-docs: ## Abre Swagger UI
	@echo "Swagger UI: http://localhost/api/v1/docs"

# ===== Calidad de código =====
lint: ## Lint Python (ruff)
	docker compose run --rm api-1 ruff check app/ || true

format: ## Format Python (black)
	docker compose run --rm api-1 black app/ || true

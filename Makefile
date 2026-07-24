# Atajos del stack. Requiere Docker Compose v2 (plugin).
# Config por variables de entorno: copia .env.example a .env antes de empezar.

DC := docker compose
DC_PROD := docker compose -f compose.yaml -f compose.prod.yaml

.DEFAULT_GOAL := help
.PHONY: help up down build seed logs test migrate revision ps psql restart clean prod-up prod-down

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Levanta el stack en desarrollo (build + hot reload) y espera a que quede sano
	$(DC) up -d --build

down: ## Detiene el stack (conserva volúmenes/datos)
	$(DC) down

build: ## Reconstruye las imágenes
	$(DC) build

seed: ## Carga el dataset (idempotente)
	$(DC) run --rm seed

logs: ## Sigue los logs de la API (usa S=db para otro servicio)
	$(DC) logs -f $(or $(S),api)

test: ## Ejecuta la batería de pruebas de la API (aplica migraciones antes)
	$(DC) run --rm api pytest -q

migrate: ## Aplica las migraciones Alembic hasta head
	$(DC) run --rm --entrypoint "" api alembic upgrade head

revision: ## Genera una migración autogenerada: make revision m="mensaje"
	$(DC) run --rm --entrypoint "" api alembic revision --autogenerate -m "$(m)"

ps: ## Estado de los servicios
	$(DC) ps

psql: ## Abre una consola psql en la base
	$(DC) exec db psql -U $${POSTGRES_USER:-inventario} -d $${POSTGRES_DB:-inventario}

restart: ## Reinicia la API
	$(DC) restart api

clean: ## Detiene y BORRA volúmenes (datos). ¡Destructivo!
	$(DC) down -v

prod-up: ## Levanta el stack en modo producción
	$(DC_PROD) up -d --build

prod-down: ## Detiene el stack de producción
	$(DC_PROD) down

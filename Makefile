COMPOSE := docker compose -f infra/docker-compose.yml

.PHONY: db-reset up migrate demo

db-reset:
	$(COMPOSE) down -v

up:
	$(COMPOSE) up -d --build

migrate:
	$(COMPOSE) exec backend bash -lc "alembic -c alembic.ini upgrade head"

demo:
	$(COMPOSE) --profile demo run --rm --no-deps demo

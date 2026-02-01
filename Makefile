.PHONY: up down status logs provision smoke reset api

up:
	@docker compose -f docker-compose.demo.yml up -d

down:
	@docker compose -f docker-compose.demo.yml down

status:
	@docker compose -f docker-compose.demo.yml ps

logs:
	@docker compose -f docker-compose.demo.yml logs -f

provision:
	@./scripts/provision_kafka_topics.sh
	@./scripts/provision_schema_registry.sh
	@./scripts/provision_postgres.sh
	@./scripts/provision_minio.sh

api:
	@python -m src.services.api_gateway

smoke:
	@./scripts/smoke.sh

reset:
	@echo "Will reset local infrastructure state and data (next prompt)."

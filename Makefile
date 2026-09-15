.PHONY: help infra-libs infra-up infra-down infra-reset infra-logs infra-ps init test lint

help:
	@echo "targets:"
	@echo "  infra-libs   download third-party jars required to build images"
	@echo "  infra-up     build images and start all services"
	@echo "  infra-down   stop all services"
	@echo "  infra-reset  stop services and remove named volumes"
	@echo "  infra-logs   tail service logs"
	@echo "  infra-ps     list running services and health"
	@echo "  init         wait for health + provision buckets/catalogs"
	@echo "  test         run the test-suite"
	@echo "  lint         run ruff"

infra-libs:
	@mkdir -p infra/trino/lib
	@test -f infra/trino/lib/postgresql.jar || \
		curl -fsSL -o infra/trino/lib/postgresql.jar \
		https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar
	@echo "infra libs present"

infra-up: infra-libs
	docker compose up -d --build

infra-down:
	docker compose down

infra-reset:
	docker compose down -v

infra-logs:
	docker compose logs -f

infra-ps:
	docker compose ps

init: infra-libs
	uv run python scripts/init_infra.py

test:
	uv run pytest

lint:
	uv run ruff check .
.PHONY: up down restart logs test clean smoke

# Default: start entire stack with docker-compose
up:
	docker compose up --build -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

# Run backend unit & integration tests
test:
	cd backend && pytest -v tests/

# Execute verification smoke test against running backend
smoke:
	@bash scripts/smoke.sh || python scripts/smoke.py

# Clean generated containers, volumes and cache files
clean:
	docker compose down -v --remove-orphans
	rm -rf backend/.pytest_cache backend/__pycache__ backend/app/__pycache__
	rm -rf frontend/dist frontend/node_modules

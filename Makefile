.PHONY: dev-backend dev-frontend test build up down logs clean

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest -q

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	rm -rf backend/data backend/test-data frontend/dist frontend/node_modules

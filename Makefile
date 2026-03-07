.PHONY: test test-fast lint dev-backend dev-frontend build-vectors

# Run full backend test suite
test:
	python -m pytest backend/tests/ -v

# Run tests without slow integration tests
test-fast:
	python -m pytest backend/tests/ -v --ignore=backend/tests/test_integration.py

# Start backend (port 8000, hot-reload)
dev-backend:
	uvicorn backend.main:app --reload --port 8000

# Start frontend (port 3000)
dev-frontend:
	cd frontend_ && npm run dev

# Rebuild ChromaDB vector index from products.json
build-vectors:
	python -c "from backend.tools import build_vector_store; build_vector_store()"

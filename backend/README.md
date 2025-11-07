# Backend

Flask API for deepfake detection.

## Running Tests

Tests require PostgreSQL. Start the database first:

```bash
# Start PostgreSQL
docker compose up -d db

# Set test database URL
export TEST_DATABASE_URL=postgresql+psycopg://deepfake:secret2@localhost:5432

# Run all tests
cd backend
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=api --cov-report=term

# Run specific test file
pytest tests/unit/test_metadata_pure.py -v
```

### Running Tests Inside Container

```bash
docker compose exec backend bash -c \
  "TEST_DATABASE_URL=postgresql+psycopg://deepfake:secret2@db:5432 \
   COVERAGE_FILE=/tmp/.coverage \
   pytest tests/ -v --cov=backend/api --cov-report=term"
```

### Test Structure

- `tests/unit/` - Pure function tests (no database)
- `tests/integration/` - API integration tests
- `tests/` - Legacy tests (auth, analysis, video upload, framerate)

All tests use PostgreSQL (no SQLite support).

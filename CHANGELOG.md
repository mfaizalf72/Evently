# Changelog

All notable changes to the **Evently** project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-12 - V1 Milestone: Foundation & Architecture

### Added
- **Clean Architecture Directory Structure**: Created modular packages for `api`, `core`, `database`, `models`, `schemas`, `services`, `repositories`, `middleware`, `integrations`, and `ai`.
- **FastAPI Core Application**: Configured `app/main.py` with application factory, lifespan management for graceful database connection pooling, and CORS middleware.
- **Pydantic v2 Configuration**: Implemented `app/core/config.py` using `pydantic_settings.BaseSettings` for strongly typed environment variables with auto-computed async/sync database URLs.
- **SQLAlchemy 2.0 Dual Engine Configuration**:
  - Asynchronous engine (`asyncpg` driver) for high-performance non-blocking API requests.
  - Synchronous engine (`psycopg` 3 driver) for Alembic schema migrations and test harness setup.
  - Per-request database dependency `get_db()` with automatic session rollback and cleanup.
  - Base declarative model `app.models.base.Base` with `TimestampMixin` and `UUIDPrimaryKeyMixin`.
- **Database Health Diagnostics**: Added `GET /api/v1/health` endpoint verifying real-time PostgreSQL database connectivity and returning structured diagnostic metadata.
- **Alembic Database Migration Harness**: Initialized Alembic migration environment dynamically bound to application settings.
- **Automated Testing Suite**:
  - Configured Pytest (`pyproject.toml`) with `pytest-asyncio` and `httpx`.
  - Implemented `tests/conftest.py` with isolated test database setup using `NullPool` and transaction rollbacks.
  - Added integration tests in `tests/integration/test_health.py` testing root endpoint, health check, and OpenAPI documentation schema.
- **Environment & Dependency Manifests**: Created `.env.example`, `.env`, `.gitignore`, `pyproject.toml`, and `requirements.txt`.
- **Project Documentation**: Created `README.md`, `ROADMAP.md` (V1–V18), and `CHANGELOG.md`.

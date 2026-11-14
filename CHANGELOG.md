# Changelog

All notable changes to the **Evently** project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-11-14 - Phase 2 Milestone (V3–V4): Authentication & Role-Based Authorization

### Added
- **User SQLAlchemy Model (`app/models/user.py`)**:
  - UUID primary key, timestamp mixin, normalized unique email, bcrypt password hash, display name, role (`organizer`, `customer`, `admin`), active status.
  - One-to-many relationship linking `User` (Organizer) with `Event`.
- **Event Ownership Schema (`app/models/event.py`)**:
  - Added `organizer_id` foreign key column referencing `users.id` with `ON DELETE CASCADE`.
- **Cryptographic Security Engine (`app/core/security.py`)**:
  - Salted password hashing and constant-time password verification via `bcrypt`.
  - Cryptographically signed JWT token generation (`create_access_token`, `create_refresh_token`) and verification (`decode_token`) via `pyjwt`.
- **Authentication & RBAC Dependencies (`app/api/deps.py`)**:
  - `OAuth2PasswordBearer` scheme integrated with Swagger UI.
  - `get_current_user` resolving active authenticated user from Bearer tokens.
  - Role-based authorization guards: `require_role`, `get_current_organizer`, and `get_current_admin`.
- **Authentication Schemas (`app/schemas/user.py` & `app/schemas/token.py`)**:
  - Pydantic v2 schemas: `UserCreate`, `UserLogin`, `UserResponse`, `Token`, `RefreshTokenRequest`.
  - Enforced password length (min 8 chars) and email format validation.
- **Auth REST Endpoints (`app/api/v1/endpoints/auth.py`)**:
  - `POST /api/v1/auth/register` (Register new user with hashed password - 201 Created).
  - `POST /api/v1/auth/login` (Authenticate credentials and issue JWT access & refresh tokens - 200 OK).
  - `POST /api/v1/auth/refresh` (Exchange valid refresh token for fresh access token - 200 OK).
  - `GET /api/v1/auth/me` (Retrieve current authenticated user profile - 200 OK).
- **Protected Event Endpoints & Ownership Verification**:
  - Event mutation routes (`POST`, `PUT`, `DELETE` in `app/api/v1/endpoints/events.py`) protected by `get_current_organizer`.
  - Service-level ownership checks preventing organizers from altering or deleting events created by other organizers.
  - Event discovery endpoints (`GET /events`, `GET /events/{id}`) remain public for event attendees.
- **Alembic Migration (`9e4cbe9cb799_create_users_table_and_add_organizer_to_.py`)**:
  - Created `users` table with unique email index and added foreign key `fk_events_organizer_id_users` to `events`.
- **Automated Test Suite (40/40 Passing)**:
  - Cryptographic security unit tests (`tests/unit/test_security.py`).
  - User registration & login schema unit tests (`tests/unit/test_user_schemas.py`).
  - Authentication API integration tests (`tests/integration/test_auth_api.py`).
  - RBAC and event ownership authorization integration tests (`tests/integration/test_event_authorization.py`).
  - Upgraded Event CRUD integration tests (`tests/integration/test_events_api.py`) with authenticated test fixtures.

## [0.2.0] - 2026-11-12 - V2 Milestone: Event Data Model & CRUD APIs

### Added
- **Event SQLAlchemy Model (`app/models/event.py`)**:
  - UUID primary key, timestamp mixin, title, description, location, start/end timestamps, total/available capacity, price, publication status.
  - PostgreSQL database-level check constraints: positive capacity, valid available capacity range, non-negative price, and valid chronological order (`end_time > start_time`).
- **Domain Exception Hierarchy (`app/core/exceptions.py`)**:
  - `EntityNotFoundException` (mapped to HTTP 404 with structured error envelope).
  - `BusinessRuleViolationException` (mapped to HTTP 400).
  - Global FastAPI exception handlers registered in `app/main.py`.
- **Pydantic v2 Event Schemas (`app/schemas/event.py`)**:
  - `EventCreate`, `EventUpdate`, `EventResponse`, `EventListResponse`, `EventFilterParams`.
  - Whitespace trimming, positive capacity checks, non-negative price, and date order cross-field validators.
- **Repository Pattern (`app/repositories/`)**:
  - `BaseRepository` generic class for type-safe asynchronous CRUD.
  - `EventRepository` supporting dynamic ILIKE queries, date ranges, price filters, total count queries, and pagination.
- **Service Layer (`app/services/event_service.py`)**:
  - Encapsulated business rules: auto-initializing available capacity, capacity reduction guards, date updates verification, and deletion restrictions on booked events.
- **Event REST Endpoints (`app/api/v1/endpoints/events.py`)**:
  - `POST /api/v1/events` (Create Event - 201 Created).
  - `GET /api/v1/events` (List Events with pagination & filtering - 200 OK).
  - `GET /api/v1/events/{event_id}` (Retrieve Event by UUID - 200 OK).
  - `PUT /api/v1/events/{event_id}` (Update Event - 200 OK).
  - `DELETE /api/v1/events/{event_id}` (Delete Event - 204 No Content).
- **Alembic Migration (`7da1523d64f2_create_events_table.py`)**:
  - Generated and executed DDL migration creating `events` table with indexes and constraints on PostgreSQL.
- **Automated Test Suite**:
  - Schema unit tests (`tests/unit/test_event_schemas.py`) covering all validation invariants.
  - Integration tests (`tests/integration/test_events_api.py`) verifying full CRUD lifecycle against isolated PostgreSQL test database.

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

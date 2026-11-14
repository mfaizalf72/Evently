# Evently Development Roadmap (V1 – V18)

This roadmap tracks the progressive development of **Evently**, an event management and ticket booking platform designed for community workshop creators, local organizers, and attendees.

Status designations:
- `NOT STARTED`
- `IN PROGRESS`
- `COMPLETED`
- `BLOCKED`

---

## Phase 1: Core Data & Foundation (V1 – V2)

| Version | Milestone | Description | Status |
| :--- | :--- | :--- | :--- |
| **V1** | **Project Initialization & Core Setup** | Empty workspace setup, clean architecture folder structure, virtual environment, FastAPI setup, PostgreSQL connection (asyncpg & psycopg), SQLAlchemy 2.0 configuration, Alembic setup, Pydantic v2 settings, health check endpoint, Pytest test runner, Git initialization. | **COMPLETED** |
| **V2** | **Event Database Model & CRUD APIs** | Event SQLAlchemy model, repository pattern, service layer, Pydantic request/response schemas, Event CRUD endpoints (create, retrieve, list with pagination/filtering, update, delete), Alembic migration for events, unit & integration tests. | **COMPLETED** |

---

## Phase 2: Security & Identity (V3 – V4)

| Version | Milestone | Description | Status |
| :--- | :--- | :--- | :--- |
| **V3** | **User Authentication & Password Hashing** | User database model, Argon2/bcrypt password hashing, user registration, login endpoint, JWT token generation (access & refresh tokens). | **COMPLETED** |
| **V4** | **Role-Based Access Control (RBAC) & Ownership** | Roles (`ORGANIZER`, `CUSTOMER`, `ADMIN`), FastAPI dependency-based authorization guards, resource ownership checks (organizers can only modify their own events). | **COMPLETED** |

---

## Phase 3: Business Logic & Concurrency Control (V5 – V10)

| Version | Milestone | Description | Status |
| :--- | :--- | :--- | :--- |
| **V5** | **Ticket Tier & Inventory Management** | Ticket tier model (VIP, General, Early Bird), pricing, seat allocation, and aggregate event capacity management. | NOT STARTED |
| **V6** | **Race-Condition-Proof Booking Engine** | High-concurrency seat reservation engine using PostgreSQL atomic conditional updates, `SELECT FOR UPDATE` row-level locks, and database check constraints to eliminate overbooking. | NOT STARTED |
| **V7** | **Idempotency & Reservation Expiration** | Idempotency keys for booking requests, temporary seat holds with automatic background expiration for unpaid orders. | NOT STARTED |
| **V8** | **Payment Integration & Webhook Verification** | Payment provider integration (Stripe/mock gateway), cryptographic webhook signature verification, atomic order state transitions from reserved to confirmed. | NOT STARTED |
| **V9** | **Ticket Issuance & Customer Booking History** | Unique digital ticket generation with verifiable QR codes / secure hashes, customer booking history endpoints. | NOT STARTED |
| **V10** | **Cancellation & Refund Management** | Order cancellation workflow, automated inventory replenishment, policy-driven refund calculation, audit logging. | NOT STARTED |

---

## Phase 4: Automation & Intelligence (V11 – V14)

| Version | Milestone | Description | Status |
| :--- | :--- | :--- | :--- |
| **V11** | **Transactional Outbox & n8n Integration** | Transactional outbox pattern to guarantee event publishing, resilient n8n webhook notifications for tickets, receipts, and organizer alerts. | NOT STARTED |
| **V12** | **Knowledge Base Ingestion & Document Chunking** | Policy document parser (refund policies, organizer guidelines, FAQs), text chunking, and metadata tagging. | NOT STARTED |
| **V13** | **Embeddings & Vector Search (RAG Pipeline)** | Vector embeddings generation, PostgreSQL pgvector integration / vector store, semantic similarity search. | NOT STARTED |
| **V14** | **AI Customer Support Agent** | Grounded RAG agent answering customer queries strictly using official policies, guardrails preventing hallucinated refunds or inventory changes, human escalation. | NOT STARTED |

---

## Phase 5: Production, Frontend & Deployment (V15 – V18)

| Version | Milestone | Description | Status |
| :--- | :--- | :--- | :--- |
| **V15** | **Docker & Docker Compose Orchestration** | Multi-stage Dockerfiles for backend and frontend, Docker Compose configuration for PostgreSQL, backend, redis/queues, and n8n. | NOT STARTED |
| **V16** | **React Customer Portal** | Responsive web client for customers: event catalog, dynamic seat selection, checkout, ticket wallet, and AI support widget. | NOT STARTED |
| **V17** | **React Organizer Dashboard** | Real-time analytics dashboard: ticket sales, capacity tracking, check-in scanner interface, event management. | NOT STARTED |
| **V18** | **CI/CD Pipeline & End-to-End Verification** | GitHub Actions workflow (linting, tests, coverage, build), staging deployment verification, load testing for concurrency. | NOT STARTED |

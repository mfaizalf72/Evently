# Evently 🎟️

> **Event Management & Ticket Booking Platform with Database-Level Concurrency Control**

Evently is a production-ready event management and ticket reservation platform engineered for local workshop hosts, community organizers, and small event creators. It serves as the **Single Source of Truth** for ticket inventory and booking lifecycle management.

---

## 1. Problem Statement

Many independent workshop hosts and local community creators manage ticket sales manually across WhatsApp messages, Excel spreadsheets, and bank transfer screenshots.

This informal workflow leads to three critical issues:
1. **Overbooking**: Multiple attendees pay for the last available ticket simultaneously because inventory checks are non-atomic.
2. **Administrative Overhead**: Organizers spend hours manually verifying transaction screenshots and reconciling spreadsheets.
3. **Poor Attendee Experience**: Customers experience confirmation delays, lack self-service booking portals, and face unclear cancellation/refund policies.

---

## 2. The Solution

Evently delivers an automated, resilient platform where the **PostgreSQL database is the authoritative source of truth**:
- **Atomic Concurrency Control**: Prevents overbooking at the database level using conditional row updates, `SELECT FOR UPDATE` locking, and database constraints.
- **FastAPI Backend**: Built on modern asynchronous Python with strict Pydantic v2 data validation.
- **Self-Service Portals**: Dedicated dashboards for attendees and event creators.
- **Automated Workflows**: Webhook-driven ticket delivery, payment confirmation, and notifications via n8n.
- **AI-Powered Customer Support**: A Retrieval-Augmented Generation (RAG) assistant answering queries strictly from official event and refund policies.

---

## 3. Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, Pydantic-Settings |
| **Database & ORM** | PostgreSQL 16+, SQLAlchemy 2.0 (Async/Sync), Alembic |
| **DB Drivers** | `asyncpg` (async API runtime), `psycopg` 3 (migrations & sync scripts) |
| **Testing** | Pytest, `pytest-asyncio`, HTTPX |
| **Security (Upcoming)** | JWT (Access & Refresh), Argon2 password hashing, Role-based Access Control |
| **Automation (Upcoming)** | n8n, Webhooks, Transactional Outbox Pattern |
| **AI / RAG (Upcoming)** | Vector Search, Policy Document Chunking, Guardrailed LLM Agents |
| **Frontend (Upcoming)** | React, TypeScript, TailwindCSS |

---

## 4. Architecture Overview

Evently employs **Clean Layered Architecture** to enforce separation of concerns, testability, and domain independence:

```
evently/
├── app/
│   ├── api/             # API routing, versioning (v1), and HTTP controllers
│   ├── core/            # Configuration (Pydantic Settings), security, global constants
│   ├── database/        # Engine initialization, session factories, get_db dependency
│   ├── models/          # SQLAlchemy 2.0 ORM entity models
│   ├── schemas/         # Pydantic request/response data contracts
│   ├── repositories/    # Database query abstractions and atomic operations
│   ├── services/        # Pure business logic and domain orchestration
│   ├── middleware/      # Cross-cutting HTTP middleware (CORS, logging, tracing)
│   ├── integrations/    # Third-party integrations (payments, webhooks, n8n)
│   └── ai/              # RAG pipeline, document parsers, vector search, support agent
├── alembic/             # Database schema migrations
├── tests/
│   ├── unit/            # Isolated unit tests
│   └── integration/     # End-to-end API and database integration tests
├── docs/                # Architecture diagrams and specifications
├── scripts/             # Utility and migration scripts
├── .env.example         # Template for environment configuration
├── pyproject.toml       # Project dependencies and tool configurations
├── README.md            # Project guide and documentation
├── ROADMAP.md           # Progressive version tracking (V1 to V18)
└── CHANGELOG.md         # Detailed milestone changelog
```

---

## 5. Getting Started

### Prerequisites

- **Python 3.11+** installed
- **PostgreSQL 16+** running locally or via Docker
- **Git**

### Installation

1. **Clone the repository** (or navigate to the project directory):
   ```bash
   cd Evently
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows PowerShell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Copy `.env.example` to `.env` and adjust the PostgreSQL credentials if needed:
   ```bash
   cp .env.example .env
   ```

5. **Ensure PostgreSQL databases exist**:
   Connect to PostgreSQL and create the development and testing databases:
   ```sql
   CREATE DATABASE evently_dev;
   CREATE DATABASE evently_test;
   ```

6. **Run Alembic migrations**:
   ```bash
   alembic upgrade head
   ```

---

## 6. Running the Application

Start the local development server with hot reload:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running, the interactive API documentation is available at:
- **Interactive Swagger UI**: [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)
- **ReDoc UI**: [http://127.0.0.1:8000/api/v1/redoc](http://127.0.0.1:8000/api/v1/redoc)
- **OpenAPI Schema**: [http://127.0.0.1:8000/api/v1/openapi.json](http://127.0.0.1:8000/api/v1/openapi.json)
- **Health Check**: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

## 7. Running the Automated Tests

Evently includes automated integration tests utilizing an isolated test database (`evently_test`):

```bash
pytest
```

For verbose output with test execution timing:
```bash
pytest -v -ra
```

---

## 8. Development Roadmap

We are following a phased milestone progression from **V1** to **V18**:
- **Phase 1 (V1–V2)**: Core Data & Event CRUD
- **Phase 2 (V3–V4)**: Security & Role-Based Authorization
- **Phase 3 (V5–V10)**: Business Logic & Race-Condition Prevention
- **Phase 4 (V11–V14)**: Automation (n8n) & Intelligence (RAG)
- **Phase 5 (V15–V18)**: User Interface (React) & Cloud Deployment

See [ROADMAP.md](ROADMAP.md) for current status.

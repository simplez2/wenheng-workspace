# Architecture

## Runtime Components

- `package/frontend`: React and Vite single-page application.
- `package/backend/app/routes`: HTTP transport and authorization boundaries.
- `package/backend/app/services`: optimization, export, configuration, and AI integration.
- `package/backend/app/word_formatter`: document parsing, formatting, and validation.
- `package/backend/app/models`: SQLAlchemy persistence models.
- `package/main.py`: packaged and Docker entry point that also serves static assets.
- `package/backend/app/main.py`: backend-only development entry point.

## Dependency Direction

Routes may depend on services and models. Services may depend on models and shared
utilities. Shared security and configuration policy lives in `app.security` and
`app.services.config_service` so both application entry points use the same rules.
Frontend code communicates only through `/api` and does not contain provider keys.

## Current Boundaries

Document round-trip and Word formatting are intentionally isolated from AI text
optimization. Existing DOCX files use structure-preserving formatting; generated
text documents use the renderer and style specification pipeline.

Administrator configuration writes are validated, whitelisted, and atomically
persisted. Provider URL validation is centralized before an outbound AI client is
created.

## Known Technical Debt

- The two FastAPI entry points still duplicate application assembly and startup hooks.
- `admin.py`, `ai_service.py`, and several React pages remain oversized modules.
- In-memory Word jobs are not shared across multiple application workers.
- Card keys are bearer credentials and legacy SSE/download URLs still support query parameters.

Future refactors should introduce one application factory, split route modules by
resource, move Word jobs to a durable queue, and replace long-lived card keys in
URLs with short-lived scoped session tokens.

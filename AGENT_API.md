# Agent API v1

Base URL:

```text
https://aipass.hxai.de/api/v1/agent
```

Interactive documentation:

- `https://aipass.hxai.de/api/v1/agent/docs`
- `https://aipass.hxai.de/api/v1/agent/openapi.json`

## Authentication

Use the user card key as a Bearer token:

```http
Authorization: Bearer YOUR_CARD_KEY
```

`X-Card-Key` remains available as a compatibility fallback, but Bearer authentication is recommended for new integrations. Do not put card keys in URLs or logs.

## Task lifecycle

```text
queued -> processing -> completed
                     -> failed -> resume
queued/processing -> stopped -> resume
```

Submissions return HTTP `202`. A task that exceeds the user or global concurrency limit stays in `queued` until a slot is available. AI provider calls are also governed by the independent global AI request limit.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/capabilities` | Formats, modes, and active limits |
| `POST` | `/tasks/text` | Submit raw text as JSON |
| `POST` | `/tasks/file` | Submit one DOCX/PDF/TXT/MD file |
| `POST` | `/batches/files` | Submit multiple files |
| `GET` | `/tasks` | List tasks |
| `GET` | `/tasks/{task_id}` | Get task status |
| `GET` | `/tasks/{task_id}/wait` | Long-poll for up to 300 seconds |
| `POST` | `/tasks/{task_id}/cancel` | Stop a queued or running task |
| `POST` | `/tasks/{task_id}/resume` | Resume a stopped task or retry a failure |
| `GET` | `/tasks/{task_id}/result` | Download one completed result |
| `GET` | `/batches/{batch_id}` | Get aggregate batch status |
| `GET` | `/batches/{batch_id}/wait` | Long-poll a batch |
| `GET` | `/batches/{batch_id}/result` | Download a completed batch ZIP |

## Examples

Submit text:

```bash
curl -X POST \
  -H "Authorization: Bearer $WENHENG_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"需要润色的内容","processing_mode":"paper_polish"}' \
  https://aipass.hxai.de/api/v1/agent/tasks/text
```

Submit one file:

```bash
curl -X POST \
  -H "Authorization: Bearer $WENHENG_API_KEY" \
  -F "file=@paper.docx" \
  -F "processing_mode=paper_polish_enhance" \
  https://aipass.hxai.de/api/v1/agent/tasks/file
```

Submit a batch:

```bash
curl -X POST \
  -H "Authorization: Bearer $WENHENG_API_KEY" \
  -F "files=@chapter-1.docx" \
  -F "files=@chapter-2.pdf" \
  -F "processing_mode=paper_polish_enhance" \
  https://aipass.hxai.de/api/v1/agent/batches/files
```

Wait for a task:

```bash
curl -H "Authorization: Bearer $WENHENG_API_KEY" \
  "https://aipass.hxai.de/api/v1/agent/tasks/TASK_ID/wait?timeout_seconds=30"
```

Download the original-format result:

```bash
curl -L \
  -H "Authorization: Bearer $WENHENG_API_KEY" \
  -o result.docx \
  "https://aipass.hxai.de/api/v1/agent/tasks/TASK_ID/result?acknowledge_academic_integrity=true"
```

Imported files are always exported in their source format. Text-only tasks may select `format=txt|md|docx|pdf`.

## Errors and tracing

Every response includes `X-Request-ID`. Clients may supply a safe request ID with the same header. API errors use a stable JSON envelope:

```json
{
  "error": {
    "code": "queue_limit_reached",
    "message": "Too many queued tasks",
    "details": null,
    "request_id": "8fd8b34b8d9cbf7e13cfd818"
  }
}
```

Use the request ID when correlating Agent logs with server logs. API keys and document content should not be written to logs.

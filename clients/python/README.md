# Wenheng Agent Client

Python SDK and CLI for the versioned Wenheng Agent API.

## Install

```bash
pip install "git+https://github.com/simplez2/wenheng-workspace.git@main#subdirectory=clients/python"
```

Configure the service URL and user card key:

```bash
export WENHENG_BASE_URL="https://aipass.hxai.de"
export WENHENG_API_KEY="YOUR_CARD_KEY"
```

PowerShell:

```powershell
$env:WENHENG_BASE_URL = "https://aipass.hxai.de"
$env:WENHENG_API_KEY = "YOUR_CARD_KEY"
```

## CLI

```bash
wenheng capabilities
wenheng submit paper.docx
wenheng submit paper.docx --wait
wenheng batch chapter-1.docx chapter-2.pdf --wait
wenheng status TASK_ID
wenheng wait TASK_ID
wenheng cancel TASK_ID
wenheng resume TASK_ID
```

Result downloads require an explicit responsibility acknowledgement:

```bash
wenheng --acknowledge-academic-integrity download TASK_ID -o .
wenheng --acknowledge-academic-integrity batch-download BATCH_ID -o results.zip
```

For unattended agents, set it once in the environment:

```bash
export WENHENG_ACKNOWLEDGE_ACADEMIC_INTEGRITY=true
```

Every metadata command writes JSON to stdout. Errors are written as JSON to stderr.

## Python SDK

```python
from wenheng_client import WenhengClient

with WenhengClient("YOUR_CARD_KEY", "https://aipass.hxai.de") as client:
    task = client.create_file("paper.docx", "paper_polish_enhance")
    task = client.wait_task(task["task_id"], timeout=3600)
    if task["result_ready"]:
        result = client.download_task(
            task["task_id"],
            acknowledge_academic_integrity=True,
        )
        result.save(".")
```

Interactive API documentation is available at:

- `https://aipass.hxai.de/api/v1/agent/docs`
- `https://aipass.hxai.de/api/v1/agent/openapi.json`

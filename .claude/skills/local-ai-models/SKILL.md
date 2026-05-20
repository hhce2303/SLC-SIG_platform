---
name: local-ai-models
description: "Use when implementing local AI/ML models, running LLMs locally, or generating datasets for training. Trigger terms: Ollama, local LLM, HuggingFace, transformers, dataset generation, JSONL, fine-tuning, local inference, embeddings, synthetic data, dataset export, ML pipeline, local model deployment, training data, codegen, apps/codegen."
argument-hint: "Describe what you need: run a local LLM, generate a dataset, or build an ML pipeline"
---

# Local AI Models & Dataset Generation

## When to Use
- Setting up **Ollama** to run LLMs locally (Llama, Mistral, Phi, Gemma, etc.)
- Integrating **HuggingFace Transformers** for local inference (embeddings, classification, NER, etc.)
- Exporting **datasets** from Django ORM / existing DB data to JSONL / CSV / Parquet
- Generating **synthetic training data** via an LLM
- Building a **Django service** that calls a local AI model instead of a cloud API
- Creating **fine-tuning datasets** from production data (instruct format, chat format)

---

## Procedure

### 1. Choose Your Local AI Backend

| Use Case | Recommended Tool | Notes |
|---|---|---|
| Run any LLM chat/completion | **Ollama** | Easiest setup, REST API on `localhost:11434` |
| Embeddings / sentence similarity | **sentence-transformers** | Pure Python, no server needed |
| Custom model (classification, NER) | **HuggingFace Transformers** | `pipeline()` abstraction |
| Fine-tuning / training | **Transformers + PEFT** | LoRA adapters, low VRAM usage |

---

### 2. Ollama Integration (Local LLM)

**Install & start:**
```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &        # starts REST API on port 11434
ollama pull llama3.2  # download a model
```

**Django service pattern (HTTP, no SDK needed):**
```python
# apps/ai_tools/services.py
import requests
import os

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

def ollama_chat(messages: list[dict], model: str = OLLAMA_DEFAULT_MODEL) -> str:
    """
    Send a chat request to a local Ollama instance.
    messages: [{"role": "user", "content": "..."}, ...]
    """
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]

def ollama_embed(text: str, model: str = "nomic-embed-text") -> list[float]:
    """Generate embeddings from a local Ollama model."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]
```

**Environment variables (never hardcode):**
```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

**Docker Compose addition (if Ollama runs as a service):**
```yaml
ollama:
  image: ollama/ollama:latest
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
  # GPU: uncomment for NVIDIA
  # deploy:
  #   resources:
  #     reservations:
  #       devices:
  #         - driver: nvidia
  #           count: all
  #           capabilities: [gpu]
```

---

### 3. HuggingFace Transformers (Local Inference)

**Install:**
```bash
pip install transformers torch sentence-transformers
```

**Embeddings (semantic search, similarity):**
```python
# apps/ai_tools/services.py
from sentence_transformers import SentenceTransformer
import numpy as np

_embed_model = None  # lazy-load singleton

def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model

def embed_text(text: str) -> list[float]:
    model = get_embed_model()
    return model.encode(text).tolist()

def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))
```

**Text classification pipeline:**
```python
from transformers import pipeline

_classifier = None

def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = pipeline(
            "text-classification",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=-1,  # -1 = CPU, 0 = first GPU
        )
    return _classifier

def classify_text(text: str) -> dict:
    result = get_classifier()(text, truncation=True, max_length=512)
    return result[0]  # {"label": "POSITIVE", "score": 0.99}
```

**IMPORTANT**: Load models as module-level singletons (lazy init). Never instantiate `pipeline()` inside a view or per-request — it takes seconds and loads GB of weights.

---

### 4. Dataset Generation

#### 4a. Export from Django ORM → JSONL (instruct format)

```python
# apps/ai_tools/services.py
import json
from pathlib import Path
from django.utils import timezone

def export_queryset_to_jsonl(
    queryset,
    output_path: str,
    row_to_example_fn,
) -> int:
    """
    Export a QuerySet to JSONL training data.
    row_to_example_fn(obj) must return a dict or None to skip.
    Returns count of written examples.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for obj in queryset.iterator(chunk_size=500):
            example = row_to_example_fn(obj)
            if example is not None:
                f.write(json.dumps(example, ensure_ascii=False) + "\n")
                count += 1
    return count

# Example usage for a chat/instruct dataset:
def export_log_dataset(output_path: str) -> int:
    from apps.logs.models import Log  # adjust import
    def to_example(log):
        if not log.description:
            return None
        return {
            "messages": [
                {"role": "user", "content": f"Resume este log: {log.title}"},
                {"role": "assistant", "content": log.description},
            ]
        }
    qs = Log.objects.filter(description__isnull=False).order_by("id")
    return export_queryset_to_jsonl(qs, output_path, to_example)
```

#### 4b. Synthetic Data Generation via LLM

```python
import json
import re

SYNTHETIC_SYSTEM = """
Eres un generador de datos de entrenamiento. Responde ÚNICAMENTE con JSON válido,
sin texto adicional, sin markdown.
"""

def generate_synthetic_examples(
    topic: str,
    n: int = 10,
    model: str = OLLAMA_DEFAULT_MODEL,
) -> list[dict]:
    """Generate synthetic instruct-format examples using a local LLM."""
    prompt = (
        f"Genera {n} ejemplos de pregunta-respuesta sobre el tema: {topic}. "
        f"Devuelve un array JSON con objetos {{\"instruction\": ..., \"response\": ...}}."
    )
    raw = ollama_chat(
        [{"role": "system", "content": SYNTHETIC_SYSTEM},
         {"role": "user", "content": prompt}],
        model=model,
    )
    # Extract JSON robustly
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError(f"LLM did not return valid JSON array. Raw: {raw[:300]}")
    return json.loads(match.group())
```

#### 4c. Dataset Export API Endpoint

```python
# apps/ai_tools/views.py
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .services import export_log_dataset

class DatasetExportView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        output_path = os.path.join("/app/datasets", "logs_dataset.jsonl")
        count = export_log_dataset(output_path)
        return Response({"exported": count, "path": output_path}, status=status.HTTP_200_OK)
```

---

### 5. Django App Setup

When creating a new `apps/ai_tools/` Django app:

1. **Register** in `config/settings/base.py` → `INSTALLED_APPS`
2. **Add URL** in `config/urls.py`
3. **No migrations needed** unless adding DB models (e.g., storing embeddings)
4. **For vector storage**: use `pgvector` (PostgreSQL) or a simple JSON field for small datasets
5. **Dependencies** to add to `requirements/base.txt`:
   ```
   requests>=2.32
   sentence-transformers>=3.0
   transformers>=4.40
   torch>=2.2          # CPU-only: torch>=2.2+cpu
   ```

---

### 6. Quality Checks

Before considering an AI integration complete:

- [ ] Model loaded as singleton (not per-request)
- [ ] Timeout set on all HTTP calls to local services
- [ ] `OLLAMA_BASE_URL` / model names read from environment variables
- [ ] No credentials or model paths hardcoded
- [ ] Dataset export uses `.iterator(chunk_size=500)` to avoid loading entire QS into RAM
- [ ] Synthetic generation validates JSON before returning
- [ ] Endpoints protected with `IsAdminUser` or `IsAuthenticated`
- [ ] Added to `requirements/` — never install packages ad-hoc inside container

---

## Common Models Reference

| Model | Size | Best For | Ollama Pull Command |
|---|---|---|---|
| `llama3.2` | 2B / 3B | General chat, code | `ollama pull llama3.2` |
| `mistral` | 7B | Instruction following | `ollama pull mistral` |
| `phi3` | 3.8B | Low VRAM, fast | `ollama pull phi3` |
| `nomic-embed-text` | 137M | Embeddings | `ollama pull nomic-embed-text` |
| `all-MiniLM-L6-v2` | 80MB | Embeddings (HF, CPU) | via sentence-transformers |
| `distilbert-*` | 66M | Classification | via transformers pipeline |

---

## See Also
- [Ollama API docs](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [HuggingFace Transformers](https://huggingface.co/docs/transformers)
- [sentence-transformers](https://www.sbert.net/)
- [PEFT / LoRA fine-tuning](https://huggingface.co/docs/peft)

---

## Implemented Architecture: apps/codegen/

This project has a fully implemented `apps/codegen/` app. Use this as the reference
when extending or debugging the code generation pipeline.

### Pipeline Flow

```
User (chatbot / API)
    │  POST /api/v1/codegen/generate/
    │  { userRequest, targetApp, tablesUsed }
    ▼
GenerateView (apps/codegen/views.py)
    │
    ├─ schema_inspector.get_schema_context(tables)
    │    SQLAlchemy inspect() → reads real DB schema (columns, FKs, indexes)
    │    env: SQLALCHEMY_DATABASE_URL
    │
    ├─ services.build_ollama_prompt(request, schema)
    │    Claude Haiku → structured few-shot prompt for local model
    │    env: ANTHROPIC_API_KEY
    │
    ├─ CodeGenAudit.objects.create(status="pending")  ← saved to DB early
    │
    ├─ services.call_local_model(prompt)
    │    HTTP POST → Ollama on dedicated LAN PC
    │    env: OLLAMA_BASE_URL (e.g. http://192.168.1.XXX:11434)
    │    env: OLLAMA_MODEL (default: qwen2.5-coder:14b)
    │    env: OLLAMA_TIMEOUT (default: 300s)
    │
    └─ audit.generated_code + audit.final_code saved → returns 201
         ↑
    Admin reviews via GET /api/v1/codegen/audits/<id>/
    Admin may edit via PATCH /api/v1/codegen/audits/<id>/  (modifies final_code)
    Admin deploys via POST /api/v1/codegen/audits/<id>/approve/
         │
         └─ services.deploy_audit()
              → backup existing files to /app/codegen_backups/<id>/
              → write final_code files to BASE_APPS_DIR/<target_app>/
              → restart Docker container (15s delay, same Docker socket pattern)
```

### Environment Variables Required

```bash
SQLALCHEMY_DATABASE_URL=mysql+pymysql://user:pass@host/sig_dailylogs
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://192.168.1.XXX:11434
OLLAMA_MODEL=qwen2.5-coder:14b
OLLAMA_TIMEOUT=300
BASE_APPS_DIR=/app/apps
CODEGEN_BACKUP_DIR=/app/codegen_backups
DOCKER_CONTAINER_NAME=daily-log-backend
```

### Ollama Setup on Dedicated PC (LAN)

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Configure to listen on all interfaces
sudo systemctl edit ollama
# Add:
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0:11434"

sudo systemctl daemon-reload
sudo systemctl restart ollama

# 3. Pull the model
ollama pull qwen2.5-coder:14b

# 4. Firewall: only allow Django server IP
sudo ufw allow from 192.168.1.YYY to any port 11434
sudo ufw deny 11434
```

### API Endpoints

| Method | URL | Description |
|---|---|---|
| POST | `/api/v1/codegen/generate/` | Trigger generation pipeline |
| GET | `/api/v1/codegen/audits/` | List all audit entries |
| GET | `/api/v1/codegen/audits/<id>/` | Full detail (includes code) |
| PATCH | `/api/v1/codegen/audits/<id>/` | Edit final_code before deploy |
| POST | `/api/v1/codegen/audits/<id>/approve/` | Deploy to filesystem + restart |
| POST | `/api/v1/codegen/audits/<id>/reject/` | Reject without deploying |

All endpoints require `IsAdminUser`.

### Key Files

- `apps/codegen/models.py` — `CodeGenAudit` model (status lifecycle)
- `apps/codegen/schema_inspector.py` — SQLAlchemy schema reader
- `apps/codegen/services.py` — full pipeline + deploy logic
- `apps/codegen/selectors.py` — read-only queries
- `apps/codegen/serializers.py` — camelCase API serializers
- `apps/codegen/views.py` — APIView endpoints
- `apps/codegen/admin.py` — Django admin with status badges

### Model Output Format Expected

The local model must wrap each file with:
```
=== views.py ===
<code>
=== serializers.py ===
<code>
=== selectors.py ===
<code>
=== urls.py ===
<code>
```
`parse_generated_code()` in services.py handles this extraction.

### Recommended Models (GPU)

| Model | Quality | Generation Time (GPU) |
|---|---|---|
| `qwen2.5-coder:14b-q4_0` | ★★★★★ | 45-90s |
| `qwen2.5-coder:7b-q4_0` | ★★★★☆ | 20-40s |
| `deepseek-coder-v2:16b-q4_0` | ★★★★★ | 60-120s |
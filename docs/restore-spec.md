# Restore Vertical Slice — Contract-First Specification

## Purpose
Provide an asynchronous API to **restore/enhance a single image** and return a processed PNG/JPEG output. This spec defines the exact contract, input/output structure, error model, telemetry, and acceptance criteria for the initial MVP.

---

## Flow (Async)

1. Client uploads an image → `POST /v1/restore` → returns `job_id`.
2. Client polls → `GET /v1/jobs/{job_id}` → receives `queued | running | succeeded | failed`.
3. When `status = succeeded` → client retrieves `result_url`.

---

## Request (multipart/form-data)

- `image`: file — jpeg/png/webp/heic (max **15 MB**)  
- `model_id`: string — e.g. `restoration/gfpgans-1.4`  
- `strength`: float `[0.1..1.0]` — default: `0.6`  
- `upscale`: int `{1, 2, 4}` — default: `1`

---

## Response — `POST /v1/restore` (201)

```json
{
  "job_id": "<uuid>",
  "status": "queued"
}
Response — GET /v1/jobs/{job_id} (200)
json
Copy code
{
  "job_id": "<uuid>",
  "status": "queued|running|succeeded|failed",
  "progress": 0.0,
  "result_url": "https://cdn.example.com/outputs/<file>.png",
  "error": null
}
Error Codes
Code	Meaning
400	Invalid input (e.g., wrong strength/upscale/model_id)
413	Payload too large
415	Unsupported media type
429	Rate limit exceeded
500	Provider/model error (details masked)
503	Feature disabled (RESTORE_ENABLED=false)

Processing & Limits
Maximum image size: 4096×4096

Must decode HEIC and fix EXIF orientation

Store all files in temporary storage → move to permanent storage only on success

result_url is generated only on success

Telemetry (Required Events)
restore.requested — job_id, model_id

restore.started — job_id

restore.succeeded — job_id, duration_ms

restore.failed — job_id, error_class

Feature Flag
If RESTORE_ENABLED=false, POST /v1/restore returns 503 Service Unavailable

Rate Limiting
Default: 10 requests per minute per IP (token bucket)

Provider Abstraction (MVP Implementation)
python
Copy code
run(image_path, model_id, strength, upscale) -> output_path
Dummy provider: simulates 1–2s delay and copies input → output (keeping format and metadata if possible).

Environment Variables (for reference)
ini
Copy code
RESTORE_ENABLED=true
MAX_IMAGE_MB=15
RESULT_BASE_URL=http://10.0.2.2:8000
STORAGE_DIR=./data
PROVIDER=generic
MODEL_DEFAULT=restoration/gfpgans-1.4
RATE_LIMIT_PER_MIN=10
Acceptance Criteria
JPEG/PNG/WEBP/HEIC (<15 MB) processed successfully

POST /v1/restore returns a job_id; polling returns succeeded with a valid result_url

Feature flag off → returns 503

Telemetry events appear in logs

5+ consecutive jobs run without memory leaks or crashes

Immutable Contract Rules (Do Not Change)
Endpoint paths, parameter names, and status codes must remain exactly as defined here.

Job state machine: queued → running → succeeded | failed

Polling interval recommendation: 1.5s

Error messages must be user-friendly and must never expose internal provider stack traces.



---

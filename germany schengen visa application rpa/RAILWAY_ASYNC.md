# Async flow (no Zoho timeout): 2 services + Redis

Form filling can take 1–2 minutes. If Zoho calls the API and waits for the PDF, the request times out. Use the **async flow** instead: Zoho gets a `job_id` immediately; a **worker** runs the job and **POSTs the PDF to a URL you provide** when done.

---

## Architecture

1. **Web service** (existing): FastAPI. New endpoint **POST /submit** accepts the same body as `/fill` plus `callback_url` (and optional `record_id`). It pushes the job to Redis and returns `{ "job_id": "...", "status": "queued" }` immediately.
2. **Worker service**: Separate process that pops jobs from Redis, runs the Playwright form filler, then **POSTs the result to your `callback_url`** (e.g. a Zoho Flow webhook).
3. **Redis**: Job queue and job state. Use Railway’s Redis addon or any Redis (e.g. Upstash) and set `REDIS_URL`.

---

## Railway setup

### 1. Add Redis

- In your Railway project: **Add service** → **Database** → **Redis** (or use an external Redis and set `REDIS_URL` in Variables).
- Copy the Redis URL and add it to **Variables** for both the API and the Worker as `REDIS_URL`.

### 2. Two services from the same repo

You already have one service (the API). Add a **second service** that runs the worker:

- **Service 1 (API)**  
  - Same repo, same Dockerfile.  
  - **Start command:** `python -m src.api` (or leave default if it already runs the API).  
  - Variables: `REDIS_URL`, plus any existing (e.g. `HEADLESS=true`).

- **Service 2 (Worker)**  
  - Same repo, same Dockerfile.  
  - **Start command:** `python -m src.worker`  
  - Variables: `REDIS_URL`, `HEADLESS=true`.

So: one codebase, one Dockerfile, two services with different start commands.

### 3. Environment variables

| Variable     | API | Worker | Notes                          |
|-------------|-----|--------|---------------------------------|
| `REDIS_URL` | ✓   | ✓      | Required for async queue        |
| `HEADLESS`  | ✓   | ✓      | `true` for Playwright           |
| `PORT`      | ✓   | -      | Only API listens on a port     |

---

## API: POST /submit

**Request (same body as `/fill` plus callback):**

```json
{
  "maid_surname": "Santos",
  "maid_first_name": "Maria",
  "maid_date_of_birth": "22.05.1990",
  "client_birth_place": "Dubai",
  "client_address": "2604 Tiara United Towers West, Business Bay, Dubai",
  "callback_url": "https://flow.zoho.com/.../webhook/...",
  "record_id": "12345"
}
```

- **callback_url** (required when Redis is used): We POST the result here when the job finishes.
- **record_id** (optional): Your record ID; we echo it in the callback so Zoho can update the right record.

**Response (immediate):**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Worker will POST result to your callback_url when done."
}
```

---

## Callback payload (we POST to your URL)

When the worker finishes, it POSTs JSON to your `callback_url`:

**Success:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "record_id": "12345",
  "status": "completed",
  "filename": "videx_Maria_Santos.pdf",
  "pdf_base64": "JVBERi0xLjQK..."
}
```

**Failure:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "record_id": "12345",
  "status": "failed",
  "error": "client_birth_place is required..."
}
```

In Zoho Flow: create a **Webhook** that receives this POST, then decode `pdf_base64` (base64 → file) and attach it to the record identified by `record_id` (or by your own tracking).

---

## Zoho flow (high level)

1. **Trigger:** When you want to generate the VIDEX (e.g. button or record created).
2. **Action: Invoke URL**  
   - URL: `https://your-api.railway.app/submit`  
   - Method: POST  
   - Body: your JSON (all maid/client/passport/travel fields) **plus**  
     - `callback_url`: URL of a Zoho Flow webhook that will receive the result.  
     - `record_id`: ID of the record to update (so the webhook knows where to attach the PDF).
3. **Response:** You get `job_id` and `status: "queued"` immediately (no long wait, no timeout).
4. **Webhook (another Flow or same):** Triggered when our worker POSTs to `callback_url`. In the webhook: read `status`; if `completed`, decode `pdf_base64` and write the file to the record (e.g. Application_Document) for `record_id`; if `failed`, handle `error`.

---

## Optional: GET /job/{job_id}

You can poll job status if you want:

```http
GET https://your-api.railway.app/job/550e8400-e29b-41d4-a716-446655440000
```

Response: `{ "job_id": "...", "status": "queued" | "processing" | "completed" | "failed", "error": "..." }`  
The main flow is still: **rely on the callback** to push the PDF to Zoho when done.

---

## If Redis is not set

- **POST /submit** returns **503** with a message that the async queue is unavailable.
- **POST /fill** still works (sync): same as before, but the request may timeout if the run is slow. Use **POST /submit + Redis + worker** to avoid timeouts.

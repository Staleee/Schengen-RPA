# Schengen RPA – Hosting Checklist

---

## Germany RPA – Deploy on Railway (step-by-step)

Use this if you only care about getting the **Germany VIDEX** service live.

### Prerequisites

- Your code is in a **GitHub repo** (the whole RPAs folder, so the repo contains the folder `germany schengen visa application rpa`).

### 1. Create the Railway project

1. Go to [railway.app](https://railway.app) and **Log in** (e.g. with GitHub).
2. Click **New Project**.
3. Choose **Deploy from GitHub repo**.
4. Select your GitHub repo (the one that contains `germany schengen visa application rpa`).
5. Railway creates **one** service from that repo.

### 2. Point the service at the Germany folder only

1. Click the **service** that was created (the box with the repo name).
2. Open **Settings** (gear or “Settings” tab).
3. Find **Root Directory** (under **Build** or **Source** or **General**).
4. Set it to exactly:
   ```text
   germany schengen visa application rpa
   ```
   No leading slash, no path – just that folder name.
5. **Save**. Railway will rebuild using only that folder.

### 3. Use the Dockerfile (not Nixpacks)

1. In the same service **Settings** → **Build**.
2. Set **Builder** to **Dockerfile** (not “Nixpacks” or “Railpack”).
3. If there is a **Dockerfile path** field, leave it as `Dockerfile`.
4. **Save**.

### 4. Get a public URL

1. Go to **Settings** → **Networking** (or **Variables** tab → “Generate domain”).
2. Click **Generate Domain** (or **Add domain**).
3. Copy the URL (e.g. `https://your-service-name.up.railway.app`). This is your **Germany API** base URL.

### 5. Deploy and check

1. Trigger a **Deploy** (or wait for the rebuild after changing Root Directory).
2. Wait for the build to finish (first build can take several minutes – Playwright + Chromium).
3. Open in the browser:
   - **Health:** `https://YOUR-GERMANY-URL/health` → should return `{"status":"healthy"}`.
   - **Usage:** `https://YOUR-GERMANY-URL/` → short usage/example.
4. To get a PDF, send a POST request to `https://YOUR-GERMANY-URL/fill` with a JSON body (see your API docs or `REQUEST_BODY_MINIMAL.md`).

### Optional: Environment variables

In the service **Settings** → **Variables** you can set:

| Variable    | Value   | Purpose                          |
|------------|--------|-----------------------------------|
| `PORT`     | `8000` | App listens on this port (default) |
| `HEADLESS` | `true` | Run browser headless (recommended) |

The Dockerfile already sets `PORT=8000` and the app reads `HEADLESS` from the environment.

### If the build fails

- **“Root Directory” / “No such file”:** The folder name must match exactly: `germany schengen visa application rpa` (with spaces).
- **“Nixpacks” or “Could not determine how to build”:** In **Settings** → **Build**, set **Builder** to **Dockerfile**.
- **Build timeout:** First build can be long (Playwright + Chromium). On a free plan, if it times out, try **Redeploy** once (cache can speed the second build), or use a plan with a longer build limit.

---

**Three separate services** (each under 4 GB, own URL):

| Service | What it does | Root Directory |
|--------|----------------|----------------------------------|
| **France** | France-Visas: register, verify email, login | `france schengen visa application rpa` |
| **Germany** | VIDEX form: fill application, generate PDF | `germany schengen visa application rpa` |
| **Documents** (future) | Generate other documents (not Schengen apps) | `document generation rpa` (or similar) |

One repo → one Railway project → one service per app → each gets its own URL. When you add the document service later, you add a third service and point it at that folder.

---

## Part 1: Put your code on GitHub

### 1. Create a new repo on GitHub

1. Go to [github.com](https://github.com) and sign in.
2. Click **+** (top right) → **New repository**.
3. Name it (e.g. `schengen-rpa` or `RPAs`).
4. Choose **Private** or **Public**.
5. **Do not** check “Add a README” (you already have code).
6. Click **Create repository**.

### 2. Push your RPAs folder to that repo

```powershell
cd "c:\Users\user\Desktop\maids.cc\RPAs"
git init
git add .
git commit -m "Initial: France + Germany Schengen RPA"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME`. Use a [Personal Access Token](https://github.com/settings/tokens) as password if Git asks.

---

## Part 2: Deploy on Railway (separate services)

Each app is **one service** with its **own Root Directory**. That way Railway builds **only that folder** for that service – not the whole repo.

---

### ⚠️ Important: Set Root Directory for each service

If you don’t set **Root Directory**, Railway uses the **whole repository** as the build context (and will use the root Dockerfile).  
**You must set Root Directory** so Railway uses only the folder you want:

- **France service** → Root Directory = `france schengen visa application rpa` (only that folder)
- **Germany service** → Root Directory = `germany schengen visa application rpa` (only that folder)

**Where to set it on Railway**

1. Click the **service** (the box with the service name).
2. Open **Settings** (gear icon or “Settings” tab).
3. Find **“Root Directory”** (sometimes under **Build** or **General**).
4. In the text field, type **only the folder name**, e.g. `france schengen visa application rpa`.
   - No leading slash, no path – just that folder name.
5. Save. Railway will rebuild using **only that folder** (and that folder’s Dockerfile).

**Can’t find Root Directory?** Look under **Settings** → **Build** (or **Source**). It might be called “Root Directory”, “Source Directory”, or “Monorepo path”. Type the folder name exactly as in your repo.

---

### ⚠️ Germany: use Dockerfile, not Railpack

If Germany fails with **“Railpack could not determine how to build”** or **“Script start.sh not found”**, Railway is using Railpack instead of the Dockerfile.

**Fix:** Germany service → **Settings** → **Build** → set **Builder** to **Dockerfile** (and **Dockerfile path** to `Dockerfile` if asked). Save and redeploy. Do the same for France if it ever shows Railpack.

---

### 3. Create a Railway project

1. Go to [railway.app](https://railway.app) → **Login** with GitHub.
2. **New Project** → **Deploy from GitHub repo**.
3. Select your repo. Railway creates **one** service.

### 4. Service 1 – France (only the France folder)

1. Click the service that was created.
2. **Settings** → find **Root Directory** → set to: `france schengen visa application rpa`
3. Save. Railway rebuilds; build context is **only** that folder.
4. **Settings** → **Networking** → **Generate Domain**.
5. Copy the URL → that’s your **France** API.

### 5. Service 2 – Germany (only the Germany folder)

1. In the **same** project, click **+ New** → **GitHub Repo**.
2. Select the **same** repo. A second service is created.
3. Click that service → **Settings** → **Root Directory** → set to: `germany schengen visa application rpa`
4. **Settings** → **Build** → set **Builder** to **Dockerfile** (not Railpack). If you see “Railpack” or “Nixpacks”, switch it to **Dockerfile** so Railway uses the folder’s `Dockerfile`.
5. Save. Build context is **only** that folder.
6. **Settings** → **Networking** → **Generate Domain**.
7. Copy the URL → that’s your **Germany** API.

### 6. Service 3 – Document generation (later)

When you add the document-generation app:

1. In the repo, create a folder for it (e.g. `document generation rpa` or `documents-rpa`) with its own Dockerfile and app.
2. Push to GitHub.
3. In the **same** Railway project: **+ New** → **GitHub Repo** → same repo.
4. New service → **Settings** → **General** → **Root Directory** = that folder (e.g. `document generation rpa`).
5. **Generate Domain** → that’s your **Documents** API.

Same pattern: one service per app, each with its own root directory and URL.

---

### Build timeouts (France / Germany)

Railway limits build time by plan (e.g. **Free: 10 min**, **Hobby: 20 min**). Both Dockerfiles are optimized to finish faster:

- **Pip cache** (`--mount=type=cache`) so rebuilds reuse downloaded packages.
- **France:** Torch (CPU) installed first so easyocr reuses it; one Playwright step.
- **Germany:** One Playwright step; pip cache.

If a build still times out, try **Hobby** plan for a longer limit, or trigger a **redeploy** (second build is often faster thanks to cache).

---

## Part 3: Check it works

| Service | Check |
|--------|--------|
| France | `https://YOUR-FRANCE-URL/health` → `{"status":"ok","service":"france-visas-automation",...}` |
| France | `https://YOUR-FRANCE-URL/docs` → Swagger UI |
| Germany | `https://YOUR-GERMANY-URL/` or `/health` → status + usage |

Endpoints stay as in the code (France: `/register-and-verify`, `/login`; Germany: `/fill`).

---

## Quick reference

| Service | Root Directory (exactly) | Purpose |
|--------|---------------------------|--------|
| France | `france schengen visa application rpa` | France-Visas registration + login |
| Germany | `germany schengen visa application rpa` | VIDEX form fill + PDF |
| Documents (future) | e.g. `document generation rpa` | Other document generation |

One repo → one Railway project → **France + Germany now, Documents when you add it**. Yalla.

---

## Part 4: Control when services update (optional)

By default, **every push to GitHub** can trigger a new deploy for services connected to that repo. If you want **GitHub updates to NOT automatically change your live services**:

### Option A: Turn off auto-deploy per service

1. Open the **service** (e.g. Germany or France).
2. Go to **Settings** → **Deploy** (or **Source**).
3. Find **“Deploy on push”** or **“Auto-deploy”** and **turn it off**.
4. Deploys will only happen when you click **Deploy** / **Redeploy** in the Railway dashboard (or via CLI).

### Option B: Deploy only from a specific branch

1. In the same **Settings** → **Source** (or **Deploy**) section.
2. Set **Branch** to e.g. `production` or `main`.
3. Only pushes to that branch trigger a deploy. Pushes to other branches (e.g. `develop`) won’t update the live service.

### Option C: Separate repo per service

Use one GitHub repo for France and another for Germany. Connect each Railway service to its own repo. Then a push to the France repo only deploys France, and a push to the Germany repo only deploys Germany.

# Schengen RPA – Hosting Checklist

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
4. Save. Build context is **only** that folder.
5. **Settings** → **Networking** → **Generate Domain**.
6. Copy the URL → that’s your **Germany** API.

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

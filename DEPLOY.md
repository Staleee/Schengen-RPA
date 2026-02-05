# Schengen RPA – Hosting Checklist

Two services, no code changes. France and Germany each get their own URL and keep their existing endpoints.

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

Open **PowerShell** or **Command Prompt** and run:

```powershell
cd "c:\Users\user\Desktop\maids.cc\RPAs"
git init
git add .
git commit -m "Initial: France + Germany Schengen RPA"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your GitHub username and the repo name you created.

If Git asks you to log in, use a [Personal Access Token](https://github.com/settings/tokens) as the password (not your GitHub password).

---

## Part 2: Deploy on Railway (one project, two services)

### 3. Create a Railway project from GitHub

1. Go to [railway.app](https://railway.app) → **Login** with GitHub.
2. Click **New Project**.
3. Choose **Deploy from GitHub repo**.
4. Select the repo you just pushed (e.g. `schengen-rpa`).
5. Railway creates **one** service. We’ll set it to Germany first, then add France.

### 4. Configure the first service (Germany)

1. Click the service that was created.
2. Go to **Settings** (or the service’s **⋮** menu) → **General**.
3. Find **Root Directory**.
4. Set it to: `germany schengen visa application rpa`
5. Save. Railway will rebuild.
6. Go to **Settings** → **Networking** (or **Deploy** tab) → **Generate Domain**.
7. Copy the URL (e.g. `https://xxx.up.railway.app`). That’s your **Germany** API.

### 5. Add the second service (France)

1. In the **same** project, click **+ New**.
2. Choose **GitHub Repo**.
3. Select the **same** repo again.
4. A second service appears. Click it.
5. **Settings** → **General** → **Root Directory**.
6. Set it to: `france schengen visa application rpa`
7. Save. Railway will rebuild (uses the Dockerfile in that folder).
8. **Settings** → **Networking** → **Generate Domain**.
9. Copy the URL. That’s your **France** API.

---

## Part 3: Check it works

| App     | What to open in browser |
|---------|--------------------------|
| France  | `https://YOUR-FRANCE-URL/health` → should see `{"status":"ok","service":"france-visas-automation",...}` |
| France  | `https://YOUR-FRANCE-URL/docs` → Swagger UI |
| Germany | `https://YOUR-GERMANY-URL/` or `/health` → should see status + usage |

Endpoints stay as they are in the code (e.g. France: `/register-and-verify`, `/login`; Germany: `/fill`).

---

## Quick reference

| App     | Root Directory (exactly)              |
|---------|--------------------------------------|
| France  | `france schengen visa application rpa` |
| Germany | `germany schengen visa application rpa` |

One repo → one Railway project → two services (one per app) → two URLs. Yalla.

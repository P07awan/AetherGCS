# AetherGCS Complete Production Deployment Guide

This guide walks you step-by-step through deploying the full **AetherGCS** stack to production for free using:
- **Database**: MongoDB Atlas (Managed Cloud MongoDB M0 Free Tier)
- **Backend & WebSockets**: Render (FastAPI Web Service)
- **Frontend**: Vercel (React Single Page Application)
- *(Optional Alternative)*: Single Cloud VPS via Docker Compose

---

## Architecture Overview

```
                      +-----------------------------+
                      |   Vercel Global CDN Edge    |
                      |   (React 19 SPA Frontend)   |
                      +--------------+--------------+
                                     |
               HTTPS REST API        |       WSS Telemetry Stream
           (/api/drones, /commands)  |      (/api/ws/telemetry ~5Hz)
                                     v
                      +-----------------------------+
                      |     Render Web Service      |
                      |    (FastAPI + WebSockets)   |
                      +--------------+--------------+
                                     |
                          TLS Encrypted Connection
                             (mongodb+srv://)
                                     v
                      +-----------------------------+
                      |     MongoDB Atlas Cloud     |
                      |       (M0 Free Tier)        |
                      +-----------------------------+
```

---

## Phase 1: Set Up MongoDB Atlas (Database)

Render does not provide a managed MongoDB service on the free tier, so we use **MongoDB Atlas**.

### 1. Create Account & Cluster
1. Sign up or log in at [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas).
2. Click **Create** to deploy a new database.
3. Select the **M0 (Free)** tier.
4. Choose your preferred cloud provider and region (choose one close to your Render region, e.g., `us-east-1` AWS or `frankfurt` for Europe).
5. Name your cluster (e.g., `aether-cluster`) and click **Create Deployment**.

### 2. Configure Database User
1. In the Atlas dashboard, navigate to **Security** > **Database Access**.
2. Click **Add New Database User**.
3. Choose **Password** Authentication:
   - **Username**: `aether_admin` (or your choice)
   - **Password**: Generate a strong password. **Save this password securely.**
4. Under **Database User Privileges**, select **Read and write to any database** (or `Built-in Role: Atlas admin`).
5. Click **Add User**.

### 3. Whitelist Network Access
Render's free tier uses dynamic outbound IPs, so your database must accept traffic from anywhere.
1. Navigate to **Security** > **Network Access**.
2. Click **Add IP Address**.
3. Click the button **Allow Access from Anywhere** (sets IP to `0.0.0.0/0`).
4. Set description to `Render Web Service` and click **Confirm**.
5. Wait ~30 seconds until the status turns active green.

### 4. Copy Your Connection String
1. Go back to **Databases** > **Clusters**.
2. Click **Connect**.
3. Select **Drivers** (Driver: `Python`, Version: `3.12 or later`).
4. Copy the connection string format:
   ```
   mongodb+srv://aether_admin:<password>@aether-cluster.xxxx.mongodb.net/?retryWrites=true&w=majority&appName=aether-cluster
   ```
5. Replace `<password>` with the user password you created in Step 2.
6. Note this URL down for Phase 2.

---

## Phase 2: Deploy Backend to Render

Render will host the FastAPI REST API and handle real-time WebSocket telemetry connections.

### Method A: Automated Deployment via Blueprint (Recommended)
Because our repository already contains a configured [`render.yaml`](file:///e:/AetherGCS/render.yaml), you can deploy with one click:
1. Go to [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** (top right) > **Blueprint**.
3. Select your repository: `P07awan/AetherGCS`.
4. Render will detect `render.yaml` and prompt you for the `MONGO_URL` secret variable.
5. Paste your MongoDB connection string from Phase 1.
6. Click **Apply**. Render will automatically build and deploy the service.

---

### Method B: Manual Web Service Setup
If you prefer setting it up manually in the Render UI:

1. In Render, click **New +** > **Web Service**.
2. Connect your GitHub repository `P07awan/AetherGCS`.
3. Fill in the service configuration:
   - **Name**: `aethergcs-backend`
   - **Region**: Choose the region closest to your MongoDB Atlas cluster (e.g. `Oregon (US West)` or `Frankfurt (EU)`).
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: `Free`

4. Add **Environment Variables** (click *Add Environment Variable*):
   | Key | Value | Description |
   | :--- | :--- | :--- |
   | `MONGO_URL` | `mongodb+srv://...` | Connection URI from Phase 1 |
   | `DB_NAME` | `aether_gcs` | Database name |
   | `CORS_ORIGINS` | `*` | Allows Vercel frontend requests |
   | `PYTHON_VERSION` | `3.11.9` | Ensures compatible Python runtime |

5. Under **Advanced Settings**:
   - **Health Check Path**: `/api/`
   - **Auto-Deploy**: `Yes`

6. Click **Deploy Web Service**.

### 5. Verify Backend Deployment
1. Wait for the build logs to show `Application startup complete` and status `Live`.
2. Render will assign you a public URL (e.g., `https://aethergcs-backend.onrender.com`).
3. Open `https://<your-backend-name>.onrender.com/api/` in your browser. You should see:
   ```json
   {"service": "gcs", "drones": 0}
   ```
4. Open `https://<your-backend-name>.onrender.com/docs` to verify the interactive Swagger API documentation.

---

## Phase 3: Deploy Frontend to Vercel

Vercel provides edge CDN caching, instant HTTPS, and zero-maintenance static hosting for the React frontend.

### 1. Import Repository into Vercel
1. Log in to [vercel.com](https://vercel.com).
2. Click **Add New...** > **Project**.
3. Choose your GitHub account and find `P07awan/AetherGCS`. Click **Import**.

### 2. Configure Build Settings
In the Project Configuration screen:
1. **Framework Preset**: Select `Create React App` (or leave on auto-detect).
2. **Root Directory**: Click **Edit** next to Root Directory and select the `frontend` folder. Click **Continue**.
3. **Build & Output Settings**:
   - Build Command: `yarn build` (default)
   - Output Directory: `build` (default)
   - Install Command: `yarn install` (default)

### 3. Add Environment Variables
Expand the **Environment Variables** section:
- **Key**: `REACT_APP_BACKEND_URL`
- **Value**: `https://aethergcs-backend.onrender.com`
  > **IMPORTANT**:
  > - Do **NOT** add a trailing slash (`/`).
  > - Use `https://`, not `http://`.
  > - Do **NOT** add `/api` at the end (the client library automatically appends `/api`).

### 4. Deploy
1. Click **Deploy**.
2. Vercel will install dependencies and compile the optimized React bundle.
3. Once completed, you will receive a domain like: `https://aether-gcs.vercel.app`.

---

## Phase 4: Production Verification Checklist

Run through these quick checks to ensure full end-to-end functionality:

1. **Dashboard Loading**: Open your Vercel URL. The mission control UI, map, and telemetry panels should load smoothly.
2. **Telemetry WebSocket**: Open DevTools (F12) > **Console** & **Network** (filter by `WS`).
   - Look for a successful WebSocket upgrade to:
     `wss://<your-backend>.onrender.com/api/ws/telemetry`
   - Status code should be `101 Switching Protocols`.
3. **Drone Creation**:
   - In the frontend sidebar, click **Add Drone**.
   - Select connection type `UDP` or `TCP` (or mock profile).
   - Verify the drone appears in the fleet list and is persisted across page reloads.
4. **Mission Planner**:
   - Create a test mission with waypoints on the map.
   - Click **Save Mission**. Verify that the mission is saved in MongoDB Atlas.
5. **Page Refresh Test**:
   - Navigate to `/missions` or another sub-route and press `F5` / Refresh.
   - Thanks to [`frontend/vercel.json`](file:///e:/AetherGCS/frontend/vercel.json), the page should reload without a 404 error.

---

## Common Pitfalls & Troubleshooting

### 1. Render Free Tier Spin-Down (Cold Starts)
- **Symptom**: The first request after 15 minutes of inactivity takes 45–60 seconds to respond.
- **Cause**: Render puts free web services to sleep when no traffic is received.
- **Solution**:
  - The frontend has auto-reconnect logic built into `telemetrySocket.js` that will automatically reconnect once the backend wakes up.
  - Optional: Use a free uptime monitor (e.g. [cron-job.org](https://cron-job.org) or [UptimeRobot](https://uptimerobot.com)) to ping `https://<backend>.onrender.com/api/` every 10 minutes to keep it warm.

### 2. CORS Errors (`Cross-Origin Request Blocked`)
- **Symptom**: Browser console shows `CORS policy: No 'Access-Control-Allow-Origin' header is present`.
- **Fix**:
  - In Render Dashboard > Environment Variables, verify `CORS_ORIGINS` is set to `*` or your exact Vercel domain (`https://aether-gcs.vercel.app`).
  - Trigger a manual deploy on Render after updating environment variables.

### 3. Database Connection Failure (`ServerSelectionTimeoutError`)
- **Symptom**: Render logs show `ServerSelectionTimeoutError: connection refused` or `timeout`.
- **Fix**:
  - Check **Security > Network Access** in MongoDB Atlas. Ensure `0.0.0.0/0` is present and active.
  - Verify that `<password>` in your `MONGO_URL` contains no unencoded special characters (e.g., if your password has `@` or `#`, URL-encode them or use an alphanumeric password).

### 4. WebSocket Failed to Connect (`SecurityError` / Mixed Content)
- **Symptom**: Console error: `Failed to construct 'WebSocket': An insecure WebSocket connection may not be initiated from a page loaded over HTTPS.`
- **Fix**:
  - Ensure `REACT_APP_BACKEND_URL` on Vercel starts with `https://`. Our frontend automatically converts `https://` to `wss://` for WebSocket connections.

---

## Alternative Deployment: Single VPS via Docker Compose

If you have a Linux VPS (DigitalOcean Droplet, AWS EC2, Hetzner, or Linode):

1. SSH into your server:
   ```bash
   ssh root@your-server-ip
   ```
2. Clone the repository and install Docker:
   ```bash
   git clone https://github.com/P07awan/AetherGCS.git
   cd AetherGCS
   ```
3. Start the entire stack:
   ```bash
   docker compose up -d --build
   ```
4. Access (Standard Port 80 - No Port Numbers in URL):
   - Frontend UI: `http://your-server-ip` or `http://your-domain.com` (no port shown)
   - Backend API: `http://your-server-ip/api` (reverse-proxied internally, no `:8000` port shown)
   - MongoDB: Shielded internally inside the private Docker network (port 27017 is not exposed to the public internet)

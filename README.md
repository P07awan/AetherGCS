# AetherGCS

A modern, web-based Multi-Drone Ground Control Station (GCS).

## Overview
AetherGCS allows operators to connect, monitor, and command multiple drones simultaneously through a sleek web interface. It consists of a fast, asynchronous Python backend for hardware communication and a modern React frontend for real-time telemetry and mission planning on an interactive map.

## Key Features
- **Multi-Drone Management**:Connect to multiple drones simultaneously via serial/COM ports (MAVLink protocol).
- **Real-Time Telemetry**:Live drone state (altitude, speed, battery, GPS) streamed at ~5Hz via WebSockets.
- **Mission Planning**:Create, edit, and manage complex flight missions with distinct waypoints and altitude profiles.
- **Command & Control**:Send real-time commands (e.g., Takeoff, Land, Return to Launch) to one or multiple drones at once.
- **Mission Library**:Save missions to the database, duplicate them, or import/export them as JSON files.
- **Command History**:Keep a logged history of all commands sent to the fleet and their execution status.

## Technology Stack

### Frontend
- **Framework**: React (Create React App / Craco)
- **Styling & UI**: Tailwind CSS, Radix UI, Lucide Icons
- **Maps**: Leaflet & React-Leaflet
- **State Management**: Zustand & React Query
- **Architecture Documentation**: See [FRONTEND_ARCHITECTURE.md](FRONTEND_ARCHITECTURE.md)
- **Deployment**: Vercel

### Backend
- **Framework**: Python 3.10+ & FastAPI
- **Real-Time**: WebSockets for telemetry broadcasting
- **Drone Comms**: PyMAVLink & PySerial
- **Database**: MongoDB (using Motor for async I/O)
- **Deployment**: Render / Docker

---

## Quick Start with Docker (Recommended)

The easiest way to run the entire AetherGCS stack (MongoDB, FastAPI backend, and React frontend) is using Docker Compose:

### 1. Start all services
```bash
docker compose up --build
```

- **Frontend**: [http://localhost](http://localhost) (runs on standard port 80 — no port shown in URL)
- **Backend API & Swagger Docs**: [http://localhost/docs](http://localhost/docs) (reverse-proxied via Nginx, no port shown)
- **MongoDB**: Internal private network (shielded from public port exposure)

### 2. Stop services
```bash
docker compose down
```

*(Optional) For live-reloading during development inside Docker:*
```bash
docker compose -f docker-compose.dev.yml up
```

---

## Manual Local Development Setup

### Prerequisites
- Node.js & Yarn
- Python 3.10+
- MongoDB (running locally on default port 27017)

### 1. Backend Setup
```bash
cd backend
python -m venv .venv

# Activate the virtual environment (Windows):
.\.venv\Scripts\activate
# On Mac/Linux: source .venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in the `backend` folder:
```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="aether_gcs"
CORS_ORIGINS="*"
```

Run the backend server:
```bash
uvicorn server:app --reload
```
The API will be available at `http://localhost:8000`.

### 2. Frontend Setup
```bash
cd frontend
yarn install
```

Create a `.env` file in the `frontend` folder:
```env
REACT_APP_BACKEND_URL=http://localhost:8000
```

Run the React app:
```bash
yarn start
```
The application will be available at `http://localhost:3000`.

---

## Production Deployment Guide

> **Detailed Walkthrough**: For an in-depth walkthrough with architecture diagrams, checklist, and troubleshooting steps, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

The recommended stack is:
- **Database**: MongoDB Atlas (Free Tier M0)
- **Backend**: Render (Web Service with WebSockets)
- **Frontend**: Vercel (Static SPA with automatic CDN edge caching)

---

### Step 1: Database Setup (MongoDB Atlas)
1. Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) and create a free M0 cluster.
2. In **Security > Database Access**, create a user with a secure password.
3. In **Security > Network Access**, click **Add IP Address** and select **Allow Access from Anywhere (`0.0.0.0/0`)** so Render can connect.
4. Click **Connect > Drivers > Python** and copy your connection string:
   ```
   mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   ```

---

### Step 2: Backend Deployment (Render)
1. Push your repository to GitHub:
   ```bash
   git add .
   git commit -m "Configure production deployment"
   git push origin main
   ```
2. Go to your [Render Dashboard](https://dashboard.render.com/) and click **New > Web Service** (or **New > Blueprint** to use `render.yaml`).
3. Connect your GitHub repository `P07awan/AetherGCS`.
4. Configure the service:
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, add:
   - `MONGO_URL`: `<your-mongodb-atlas-connection-string>`
   - `DB_NAME`: `aether_gcs`
   - `CORS_ORIGINS`: `*`
   - `PYTHON_VERSION`: `3.11.9`
6. Click **Deploy Web Service**.
7. Once deployed, copy your backend URL (e.g., `https://aethergcs-backend.onrender.com`). Verify it by visiting `https://aethergcs-backend.onrender.com/api/` in your browser (should return `{"service": "gcs", ...}`).

---

### Step 3: Frontend Deployment (Vercel)
1. Go to [Vercel](https://vercel.com/) and click **Add New > Project**.
2. Import your GitHub repository `P07awan/AetherGCS`.
3. In the project configuration:
   - **Framework Preset**: `Create React App`
   - **Root Directory**: Click *Edit* and select `frontend`
4. Expand **Environment Variables** and add:
   - `REACT_APP_BACKEND_URL`: `https://<your-render-backend-subdomain>.onrender.com` *(no trailing slash!)*
5. Click **Deploy**.
6. Vercel will build the frontend and provide your production URL (e.g., `https://aether-gcs.vercel.app`).

---

### Step 4: Verification
- Open your Vercel URL in your browser.
- Open the Developer Tools (F12) -> Network / Console tab.
- Verify that API calls to `/api/drones` succeed (200 OK) and the WebSocket connection to `/api/ws/telemetry` connects successfully with real-time status.


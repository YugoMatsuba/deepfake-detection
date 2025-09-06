# Deepfake AI Forensics Tool

## Structure
- `backend/`: Flask API (auth, analysis pipeline)
- `frontend/`: React + Vite + Tailwind (UI)

## Quickstart (Dev)

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Backend runs on port 5050 (configurable via `PORT` env).

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Frontend runs on port 5173 by default, with `/api` requests proxied to backend.

### Login
- Username: `admin`
- Password: `testpass123`

## Environment Variables

See `.env.example` for configuration options.

## Demo

This is intended to be a sprint 1 demo just to get familiar with the tech stack. Features are:
- Session-based auth
- Environment configuration  
- SPA architecture with React Router
- Frontend to backend integration
- sqlite db (to be moved to Postgres for prod)

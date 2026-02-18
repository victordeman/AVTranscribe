# AVTranscribe

Open-source production-ready audio/video transcription system using Whisper, FastAPI, and Celery.

## Setup
1. Clone repo: `git clone https://github.com/victordeman/AVTranscribe.git`
2. Install deps: `pip install -r requirements.txt`
3. Install FFmpeg: `apt install ffmpeg` (or brew on Mac)
4. Run locally: See docker-compose.yml for full stack.

## Architecture
- Backend: FastAPI
- Tasks: Celery + Redis
- DB: PostgreSQL/SQLite
- Frontend: Jinja2 + HTMX

Deployment: Docker on VPS like DigitalOcean.

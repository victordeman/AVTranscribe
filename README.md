# AVTranscribe

AVTranscribe is a production-ready, open-source audio and video transcription system. It leverages OpenAI's Whisper for high-accuracy AI transcription, FastAPI for a modern web interface, and Celery with Redis for robust background task processing.

## 🚀 Key Features

- **AI-Powered Transcription**: High-accuracy transcription using OpenAI's Whisper models.
- **Audio & Video Support**: Handles various formats including MP3, WAV, MP4, AVI, and MOV.
- **Language Detection**: Automatically detects the spoken language or allows manual selection.
- **Asynchronous Processing**: Scalable background task management with Celery and Redis.
- **Multiple Export Formats**: Download transcriptions as plain text or CSV files.
- **Rate Limiting**: Integrated protection against abuse using SlowAPI.
- **Dockerized**: Easy deployment with Docker Compose.
- **Monitoring**: Built-in Prometheus metrics and Grafana dashboard support.
- **GPU Support**: Optional GPU-enabled Docker image for faster processing.
- **Secure**: Optional Basic Authentication for public deployments.
- **Modern UI**: Simple and responsive interface powered by Jinja2 and HTMX.

## 📸 Screenshots

![Home Page](https://via.placeholder.com/800x450?text=AVTranscribe+Home+Page)
*The main upload interface.*

![Status Tracking](https://via.placeholder.com/800x450?text=AVTranscribe+Status+Tracking)
*Real-time task progress monitoring.*

## 🛠 Tech Stack

- **Backend**: FastAPI (Python)
- **Task Queue**: Celery + Redis
- **AI Model**: OpenAI Whisper
- **Database**: SQLAlchemy (supports SQLite, PostgreSQL, etc.)
- **Frontend**: Jinja2 + HTMX + Tailwind CSS (via CDN)
- **Logging**: Structured logging with structlog

## 📂 Project Structure

```text
.
├── src/
│   ├── templates/          # HTML templates (Jinja2 + HTMX)
│   ├── main.py             # FastAPI application and API routes
│   ├── models.py           # SQLAlchemy database models
│   ├── tasks.py            # Celery task definitions
│   ├── transcribe.py       # Whisper transcription logic
│   └── utils.py            # Helper functions (validation, ETL)
├── tests/                  # Pytest suite
├── static/                 # Static files (CSS, JS)
├── Dockerfile              # Docker configuration for web/worker
├── docker-compose.yml      # Multi-container orchestration
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation
```

## 📋 Prerequisites

- **Python**: 3.12 or higher
- **FFmpeg**: Required by Whisper for media processing.
- **Redis**: Required for the Celery task queue.

## ⚙️ Local Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/victordeman/AVTranscribe.git
   cd AVTranscribe
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   Note: On Python 3.12+, `setuptools` and `wheel` are required to build some dependencies.
   ```bash
   pip install setuptools wheel
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Create a `.env` file based on `.env.example`:
   ```bash
   cp .env.example .env
   ```
   *Edit `.env` to configure your Redis and Database URLs.*

5. **Start Redis**:
   Ensure Redis is running on your system (default: `localhost:6379`).

## 🏃 Running the Application

You need to run both the FastAPI server and the Celery worker.

### 1. Start the FastAPI Server
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.main:app --bind 0.0.0.0:8000
```
Or for development:
```bash
uvicorn src.main:app --reload
```

### 2. Start the Celery Worker
```bash
celery -A src.tasks worker --loglevel=info
```

The application will be available at `http://localhost:8000`.

## 🐳 Running with Docker

The easiest way to run the full stack is using Docker Compose:

```bash
docker-compose up --build
```

This starts the web server, Celery worker, Redis, and a PostgreSQL database.

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Home page / UI |
| `POST` | `/transcribe` | Upload media for transcription |
| `GET` | `/status/{task_id}` | Check transcription status |
| `GET` | `/download/{task_id}/{fmt}` | Download result (`text` or `csv`) |

## 🧪 Testing

Run the test suite using `pytest`:

```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
pytest
```

## 🏗 Architecture Overview

1. **Upload**: User uploads a file via the FastAPI endpoint.
2. **Validation**: The file is validated (type and size) and saved temporarily.
3. **Queueing**: A transcription task is created in the database and dispatched to Celery.
4. **Processing**: A Celery worker picks up the task, uses Whisper to transcribe the media, and generates a CSV output.
5. **Completion**: The database is updated with the result, and the temporary file is removed.
6. **Delivery**: The user can check the status and download the final transcription.

## 📜 Environment Variables

- `REDIS_URL`: Connection string for Redis (default: `redis://localhost:6379/0`).
- `DB_URL`: Connection string for the database (default: `sqlite:///transcriptions.db`).
- `WHISPER_MODEL`: Whisper model size (options: `tiny`, `base`, `small`, `medium`, `large`).
- `RATE_LIMIT`: API rate limit (default: `10/minute`).
- `AUTH_USERNAME`: Username for Basic Auth (leave empty to disable).
- `AUTH_PASSWORD`: Password for Basic Auth (leave empty to disable).

## 🚀 Deployment Guide (VPS - DigitalOcean/Linode)

For a production deployment on a VPS, follow these steps:

### 1. Provision a Server
- Choose a VPS with at least 4GB RAM (Whisper models can be memory-intensive).
- For faster processing, consider a GPU-enabled instance.

### 2. Install Docker & Docker Compose
Follow the official guides for your distribution (e.g., [Ubuntu](https://docs.docker.com/engine/install/ubuntu/)).

### 3. Clone and Configure
```bash
git clone https://github.com/victordeman/AVTranscribe.git
cd AVTranscribe
cp .env.example .env
```
Update `.env` with secure passwords and your domain name.

### 4. Deploy
**Standard Deployment:**
```bash
docker-compose up -d
```

**GPU Deployment:**
Ensure you have the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) installed.
```bash
docker build -f Dockerfile.gpu -t avtranscribe:gpu .
# Update docker-compose.yml to use the 'avtranscribe:gpu' image and add 'deploy: resources: reservations: devices: - driver: nvidia ...'
```

### 5. Access Monitoring
- **Prometheus**: `http://your-vps-ip:9090`
- **Grafana**: `http://your-vps-ip:3000` (Default login: `admin/admin`)

## 🔗 Live Demo
[Coming Soon!](#)

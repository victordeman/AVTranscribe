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
- **Modern UI**: Simple and responsive interface powered by Jinja2 and HTMX.

## 🛠 Tech Stack

- **Backend**: FastAPI (Python)
- **Task Queue**: Celery + Redis
- **AI Model**: OpenAI Whisper
- **Database**: SQLAlchemy (supports SQLite, PostgreSQL, etc.)
- **Frontend**: Jinja2 + HTMX + Tailwind CSS (via CDN)
- **Logging**: Structured logging with structlog

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

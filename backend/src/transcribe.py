import os
import structlog
import sys
import io
import re
import contextvars
from typing import Any, Dict, Callable, Optional

logger = structlog.get_logger()

# Global model cache
_MODELS = {}

# Context variable for thread-safe progress tracking
_PROGRESS_CALLBACK = contextvars.ContextVar("_progress_callback", default=None)

def get_model(model_name: str):
    """Retrieves or loads a Whisper model."""
    import whisper
    import torch
    if model_name not in _MODELS:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading Whisper model", model=model_name, device=device)
        _MODELS[model_name] = whisper.load_model(model_name, device=device)
    return _MODELS[model_name]

class ProgressStdout(io.TextIOBase):
    """
    A custom stdout wrapper to detect Whisper segments during transcription.
    Uses contextvars for thread-safe callback execution.
    Whisper prints segments when verbose=True.
    Format: [00:00.000 --> 00:05.000] or [00:00:00.000 --> 00:00:05.000]
    """
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout
        # Regex handles both MM:SS.mmm and HH:MM:SS.mmm formats
        self.segment_pattern = re.compile(r"\[(?:\d+:)?\d{2}:\d{2}\.\d{3} --> (?:\d+:)?\d{2}:\d{2}\.\d{3}\]")

    def write(self, s):
        callback = _PROGRESS_CALLBACK.get()
        if callback:
            # findall() to catch multiple segments in one flush
            matches = self.segment_pattern.findall(s)
            for _ in matches:
                try:
                    callback()
                except Exception:
                    pass
        return self.original_stdout.write(s)

    def flush(self):
        return self.original_stdout.flush()

# Globally patch stdout once to handle all threads safely via ContextVar
def patch_stdout():
    if not isinstance(sys.stdout, ProgressStdout):
        sys.stdout = ProgressStdout(sys.stdout)

patch_stdout()

def detect_language_fallback(text: str) -> str:
    """
    Fallback language detection using langdetect.
    Defaults to 'en' if detection fails.
    """
    try:
        from langdetect import detect
        if not text or len(text.strip()) < 5:
            return "en"
        return detect(text)
    except Exception as e:
        logger.warning("langdetect failed, defaulting to 'en'", error=str(e))
        return "en"

def transcribe_with_openai_api(file_path: str, language: str = "auto", task: str = "transcribe") -> Dict[str, Any]:
    """
    Transcribes a media file using the OpenAI Whisper API.
    Note: Real-time progress is not supported for OpenAI API.
    """
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    logger.info("Starting OpenAI API Whisper task", file=file_path, language=language, task=task)

    with open(file_path, "rb") as audio_file:
        lang = None if language == "auto" else language

        if task == "translate":
            response = client.audio.translations.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json"
            )
        else:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=lang,
                response_format="verbose_json"
            )

    result = response.model_dump()
    
    # Language detection fallback for OpenAI API
    if language == "auto" and not result.get("language"):
        result["language"] = detect_language_fallback(result.get("text", ""))
        
    return result

def transcribe_with_whisper(
    file_path: str,
    language: str = "auto",
    task: str = "transcribe",
    on_segment: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Transcribes a media file using either local Whisper or OpenAI API.
    
    Args:
        file_path: Path to the media (audio or video) file.
        language: Language code or "auto" for detection.
        task: Whisper task type ("transcribe" or "translate").
        on_segment: Callback triggered for each transcribed segment (local only).
        
    Returns:
        The full Whisper result dictionary.
    """
    if os.getenv("OPENAI_API_KEY") or os.getenv("USE_OPENAI_API") == "true":
        try:
            return transcribe_with_openai_api(file_path, language, task)
        except Exception as e:
            if os.getenv("USE_OPENAI_API") == "true":
                logger.error("OpenAI API task failed", file=file_path, error=str(e))
                raise
            logger.warning("OpenAI API failed, falling back to local whisper", error=str(e))

    try:
        model_name = os.getenv("WHISPER_MODEL", "base")
        model = get_model(model_name)
        
        lang = None if language == "auto" else language
        
        logger.info("Starting local Whisper task", file=file_path, language=language, task=task, model=model_name)

        if on_segment:
            token = _PROGRESS_CALLBACK.set(on_segment)
            try:
                # Local whisper handles both audio and video using ffmpeg.
                result = model.transcribe(file_path, language=lang, task=task, verbose=True)
            finally:
                _PROGRESS_CALLBACK.reset(token)
        else:
            result = model.transcribe(file_path, language=lang, task=task)
        
        # Language detection fallback for local Whisper
        if language == "auto" and (not result.get("language") or result.get("language") == "unknown"):
            result["language"] = detect_language_fallback(result.get("text", ""))

        return result
    except ImportError:
        logger.error("Local Whisper not available. Please set OPENAI_API_KEY.")
        raise RuntimeError("Whisper dependencies not installed. Provide OPENAI_API_KEY for serverless mode.")
    except Exception as e:
        logger.error("Local Whisper task failed", file=file_path, task=task, error=str(e))
        raise

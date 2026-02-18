import os
import whisper
import torch
import structlog
from typing import Optional

logger = structlog.get_logger()

# Global model cache
_MODELS = {}

def get_model(model_name: str):
    """Retrieves or loads a Whisper model."""
    if model_name not in _MODELS:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading Whisper model", model=model_name, device=device)
        _MODELS[model_name] = whisper.load_model(model_name, device=device)
    return _MODELS[model_name]

def transcribe_with_whisper(file_path: str, language: str = "auto", format: str = "auto") -> str:
    """
    Transcribes a media file using Whisper.
    
    Args:
        file_path: Path to the media (audio or video) file.
        language: Language code or "auto" for detection.
        format: Hint about the format ("audio", "video", or "auto").

    Returns:
        The transcribed text.
    """
    try:
        model_name = os.getenv("WHISPER_MODEL", "base")
        model = get_model(model_name)

        # Whisper handles both audio and video files directly using ffmpeg.
        # It also handles auto-detection if language is None.
        lang = None if language == "auto" else language

        logger.info("Starting transcription", file=file_path, language=language)
        result = model.transcribe(file_path, language=lang)

        return result["text"].strip()
    except Exception as e:
        logger.error("Transcription failed", file=file_path, error=str(e))
        raise

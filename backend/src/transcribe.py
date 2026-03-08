import os
import structlog
from typing import Any, Dict

logger = structlog.get_logger()

# Global model cache
_MODELS = {}

def get_model(model_name: str):
    """Retrieves or loads a Whisper model."""
    import whisper
    import torch
    if model_name not in _MODELS:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading Whisper model", model=model_name, device=device)
        _MODELS[model_name] = whisper.load_model(model_name, device=device)
    return _MODELS[model_name]

def transcribe_with_openai_api(file_path: str, language: str = "auto", task: str = "transcribe") -> Dict[str, Any]:
    """
    Transcribes a media file using the OpenAI Whisper API.
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

    # Adapt the response to match the structure expected by the app
    # Whisper API response in 'verbose_json' includes 'text' and 'segments'
    return response.model_dump()

def transcribe_with_whisper(file_path: str, language: str = "auto", task: str = "transcribe") -> Dict[str, Any]:
    """
    Transcribes a media file using either local Whisper or OpenAI API.
    
    Args:
        file_path: Path to the media (audio or video) file.
        language: Language code or "auto" for detection.
        task: Whisper task type ("transcribe" or "translate").
        
    Returns:
        The full Whisper result dictionary.
    """
    # Use OpenAI API if requested or if local whisper is not suitable (e.g., on Vercel)
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
        
        # Whisper handles both audio and video files directly using ffmpeg.
        # It also handles auto-detection if language is None.
        lang = None if language == "auto" else language
        
        logger.info("Starting local Whisper task", file=file_path, language=language, task=task, model=model_name)
        result = model.transcribe(file_path, language=lang, task=task)
        
        return result
    except ImportError:
        logger.error("Local Whisper not available. Please set OPENAI_API_KEY.")
        raise RuntimeError("Whisper dependencies not installed. Provide OPENAI_API_KEY for serverless mode.")
    except Exception as e:
        logger.error("Local Whisper task failed", file=file_path, task=task, error=str(e))
        raise

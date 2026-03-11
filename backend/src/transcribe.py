import os
import structlog
import io
import re
import contextvars
from typing import Any, Dict, Callable, Optional, List

logger = structlog.get_logger()

# Global model cache
_MODELS = {}

def get_model(model_name: str):
    """Retrieves or loads a Faster-Whisper model."""
    from faster_whisper import WhisperModel
    import torch
    if model_name not in _MODELS:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        logger.info("Loading Faster-Whisper model", model=model_name, device=device, compute_type=compute_type)
        _MODELS[model_name] = WhisperModel(model_name, device=device, compute_type=compute_type)
    return _MODELS[model_name]

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
    Note: Real-time progress and Diarization are not supported for OpenAI API in this implementation.
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

def diarize_audio(file_path: str) -> List[Dict[str, Any]]:
    """
    Performs speaker diarization using pyannote.audio.
    Requires HF_TOKEN environment variable for gated models.
    """
    try:
        from pyannote.audio import Pipeline
        import torch
    except ImportError:
        logger.warning("pyannote.audio not installed, skipping diarization")
        return []

    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        logger.warning("HF_TOKEN not set, pyannote.audio may fail for gated models")

    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))

        logger.info("Starting diarization", file=file_path)
        diarization = pipeline(file_path)

        speaker_segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speaker_segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })
        return speaker_segments
    except Exception as e:
        logger.error("Diarization failed", error=str(e))
        return []

def merge_speakers(whisper_segments: List[Dict[str, Any]], speaker_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merges Whisper transcription segments with speaker diarization info.
    Assigns the most frequent speaker in the segment's time range.
    """
    if not speaker_segments:
        return whisper_segments

    merged = []
    for seg in whisper_segments:
        seg_start = seg["start"]
        seg_end = seg["end"]

        # Find all speaker turns that overlap with this Whisper segment
        overlaps = []
        for spk in speaker_segments:
            overlap_start = max(seg_start, spk["start"])
            overlap_end = min(seg_end, spk["end"])
            if overlap_start < overlap_end:
                overlaps.append((spk["speaker"], overlap_end - overlap_start))

        if overlaps:
            # Assign speaker with maximum overlap duration
            speaker_durations = {}
            for spk, duration in overlaps:
                speaker_durations[spk] = speaker_durations.get(spk, 0) + duration
            assigned_speaker = max(speaker_durations, key=speaker_durations.get)
            seg["speaker"] = assigned_speaker
        else:
            seg["speaker"] = "UNKNOWN"

        merged.append(seg)
    return merged

def transcribe_with_whisper(
    file_path: str,
    language: str = "auto",
    task: str = "transcribe",
    diarize: bool = False,
    on_segment: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Transcribes a media file using either Faster-Whisper or OpenAI API.
    
    Args:
        file_path: Path to the media (audio or video) file.
        language: Language code or "auto" for detection.
        task: Whisper task type ("transcribe" or "translate").
        diarize: Whether to perform speaker diarization.
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
            logger.warning("OpenAI API failed, falling back to local faster-whisper", error=str(e))

    try:
        model_name = os.getenv("WHISPER_MODEL", "base")
        model = get_model(model_name)
        
        lang = None if language == "auto" else language
        
        logger.info("Starting Faster-Whisper task", file=file_path, language=language, task=task, model=model_name)

        # Faster-whisper transcribe returns (segments_generator, info)
        segments_gen, info = model.transcribe(
            file_path,
            language=lang,
            task=task,
            beam_size=5
        )

        segments = []
        full_text = []
        for segment in segments_gen:
            seg_dict = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text
            }
            segments.append(seg_dict)
            full_text.append(segment.text)
            if on_segment:
                try:
                    on_segment()
                except Exception:
                    pass
        
        result = {
            "text": "".join(full_text).strip(),
            "segments": segments,
            "language": info.language
        }

        # Speaker Diarization
        if diarize:
            speaker_segments = diarize_audio(file_path)
            if speaker_segments:
                result["segments"] = merge_speakers(result["segments"], speaker_segments)

        # Language detection fallback
        if language == "auto" and (not result.get("language") or result.get("language") == "unknown"):
            result["language"] = detect_language_fallback(result.get("text", ""))

        return result
    except ImportError as e:
        logger.error("Faster-Whisper or dependencies not available", error=str(e))
        raise RuntimeError("Faster-Whisper dependencies not installed. Provide OPENAI_API_KEY for serverless mode.")
    except Exception as e:
        logger.error("Faster-Whisper task failed", file=file_path, task=task, error=str(e))
        raise

import whisper
import moviepy.editor as mp
import torch
import structlog
import os

logger = structlog.get_logger()

def transcribe_with_whisper(file_path: str, language: str, format: str) -> str:
    model_name = os.getenv("WHISPER_MODEL", "base")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model(model_name, device=device)
    logger.info("Loaded Whisper model", model=model_name, device=device)
    
    working_file_path = file_path
    audio_path = None

    # Extract audio if video
    if format == "video" or (format == "auto" and file_path.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))):
        logger.info("Extracting audio from video", file_path=file_path)
        video = mp.VideoFileClip(file_path)
        audio_path = file_path + ".wav"
        video.audio.write_audiofile(audio_path)
        working_file_path = audio_path

    # Whisper handles auto-detection if language is None
    lang = None if language == "auto" else language
    
    logger.info("Starting transcription", file_path=working_file_path, language=lang)
    result = model.transcribe(working_file_path, language=lang)
    
    # Cleanup extracted audio
    if audio_path and os.path.exists(audio_path):
        try:
            os.remove(audio_path)
        except Exception as e:
            logger.warning("Failed to remove extracted audio file", path=audio_path, error=str(e))

    return result["text"]

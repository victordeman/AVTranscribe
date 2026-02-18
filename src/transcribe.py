import whisper
import moviepy.editor as mp
from langdetect import detect
from pydub import AudioSegment
import torch
import structlog

logger = structlog.get_logger()

def transcribe_with_whisper(file_path: str, language: str, format: str) -> str:
    model_name = os.getenv("WHISPER_MODEL", "base")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model(model_name, device=device)
    logger.info("Loaded Whisper model", model=model_name, device=device)
    
    if format == "video" or (format == "auto" and file_path.lower().endswith((".mp4", ".avi", ".mov"))):
        video = mp.VideoFileClip(file_path)
        audio_path = file_path + ".wav"
        video.audio.write_audiofile(audio_path)
        file_path = audio_path
    
    if language == "auto":
        audio = AudioSegment.from_file(file_path)
        sample_path = "/tmp/sample.wav"
        audio[:10000].export(sample_path, format="wav")
        with open(sample_path, "rb") as f:
            lang = detect(f.read())
        os.remove(sample_path)
    else:
        lang = language
    
    result = model.transcribe(file_path, language=lang)
    if file_path.endswith(".wav") and file_path != audio_path:  # Cleanup extracted audio
        os.remove(file_path)
    return result["text"]

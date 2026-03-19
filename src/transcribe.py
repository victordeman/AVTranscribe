import os
import structlog
import httpx
from typing import Optional, Any, Dict

logger = structlog.get_logger()

# Global model cache
_PIPES = {}

def get_pipeline(model_id: str):
    """Retrieves or loads a Hugging Face transcription pipeline."""
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    if model_id not in _PIPES:
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        logger.info("Loading Distil-Whisper model", model=model_id, device=device)

        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True
        )
        model.to(device)

        processor = AutoProcessor.from_pretrained(model_id)

        _PIPES[model_id] = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            max_new_tokens=128,
            chunk_length_s=30,
            batch_size=16,
            torch_dtype=torch_dtype,
            device=device,
        )
    return _PIPES[model_id]

def transcribe_with_hf_api(file_path: str, language: str = "auto", task: str = "transcribe") -> Dict[str, Any]:
    """
    Transcribes a media file using the Hugging Face Inference API.
    """
    hf_token = os.getenv("HF_TOKEN")
    model_id = os.getenv("HF_MODEL_ID", "distil-whisper/distil-large-v3")
    api_url = f"https://api-inference.huggingface.co/models/{model_id}"

    headers = {"Authorization": f"Bearer {hf_token}"}

    logger.info("Starting Hugging Face API task", file=file_path, model=model_id)

    with open(file_path, "rb") as f:
        data = f.read()

    # HF Inference API for ASR
    params = {
        "wait_for_model": True,
        "return_timestamps": "true" # Request timestamps for segments/chunks
    }
    if language != "auto":
        params["language"] = language

    response = httpx.post(api_url, headers=headers, content=data, params=params, timeout=300)

    if response.status_code != 200:
        logger.error("HF API request failed", status=response.status_code, error=response.text)
        raise RuntimeError(f"HF API request failed: {response.text}")

    result = response.json()
    # Normalize response to match the expected structure {'text': ..., 'segments': ...}
    # HF Inference API returns 'chunks' when timestamps are requested.
    return {
        "text": result.get("text", ""),
        "segments": result.get("chunks", [])
    }

def transcribe_with_whisper(file_path: str, language: str = "auto", task: str = "transcribe") -> Dict[str, Any]:
    """
    Transcribes a media file using either local Distil-Whisper or HF API.
    """
    # Use HF API if token is provided or specifically requested
    if os.getenv("HF_TOKEN") or os.getenv("USE_HF_API") == "true":
        try:
            return transcribe_with_hf_api(file_path, language, task)
        except Exception as e:
            if os.getenv("USE_HF_API") == "true":
                logger.error("Hugging Face API task failed", file=file_path, error=str(e))
                raise
            logger.warning("Hugging Face API failed, falling back to local model", error=str(e))

    try:
        # Fallback to local Distil-Whisper
        model_id = os.getenv("HF_MODEL_ID", "distil-whisper/distil-large-v3")
        pipe = get_pipeline(model_id)
        
        logger.info("Starting local Distil-Whisper task", file=file_path, language=language, task=task, model=model_id)

        generate_kwargs = {"task": task}
        if language != "auto":
            generate_kwargs["language"] = language

        # For long-form audio (>30s), chunking is handled by the pipeline settings in get_pipeline
        result = pipe(file_path, generate_kwargs=generate_kwargs, return_timestamps=True)
        
        # Normalize result format
        return {
            "text": result.get("text", ""),
            "segments": result.get("chunks", []) # transformers pipeline uses 'chunks' for timestamps
        }
        
    except ImportError:
        logger.error("Transformers/Torch not available. Please set HF_TOKEN or install requirements-local.txt.")
        raise RuntimeError("Local dependencies not installed. Provide HF_TOKEN for serverless mode.")
    except Exception as e:
        logger.error("Local Distil-Whisper task failed", file=file_path, error=str(e))
        raise

import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# Mock faster-whisper and torch for the entire module if they don't exist
sys.modules['faster_whisper'] = MagicMock()
sys.modules['torch'] = MagicMock()
sys.modules['pyannote.audio'] = MagicMock()

import src.transcribe
from src.transcribe import transcribe_with_whisper, _MODELS

@pytest.fixture(autouse=True)
def clear_models_cache():
    _MODELS.clear()

@patch("src.transcribe.get_model")
def test_transcribe_with_whisper_success(mock_get_model):
    # Setup mock model
    mock_model = MagicMock()

    mock_segment = MagicMock()
    mock_segment.start = 0.0
    mock_segment.end = 1.0
    mock_segment.text = "Hello world"

    mock_info = MagicMock()
    mock_info.language = "en"

    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    mock_get_model.return_value = mock_model
    
    # Execute
    result = transcribe_with_whisper("dummy_path.mp3", language="en")
    
    # Assertions
    assert result["text"] == "Hello world"
    mock_model.transcribe.assert_called_once()

@patch("src.transcribe.get_model")
def test_transcribe_with_whisper_on_segment(mock_get_model):
    # Setup mock model
    mock_model = MagicMock()
    
    mock_segment = MagicMock()
    mock_segment.start = 0.0
    mock_segment.end = 1.0
    mock_segment.text = "Hello world"
    
    mock_info = MagicMock()
    mock_info.language = "en"

    mock_model.transcribe.return_value = ([mock_segment, mock_segment], mock_info)
    mock_get_model.return_value = mock_model
    
    # Callback
    on_segment = MagicMock()

    # Execute
    result = transcribe_with_whisper("dummy_path.mp3", on_segment=on_segment)
    
    # Assertions
    assert result["text"] == "Hello worldHello world"
    assert on_segment.call_count == 2

@patch("src.transcribe.get_model")
def test_transcribe_with_whisper_error(mock_get_model):
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = Exception("Whisper error")
    mock_get_model.return_value = mock_model
    
    with pytest.raises(Exception) as excinfo:
        transcribe_with_whisper("bad_file.mp3")
    
    assert "Whisper error" in str(excinfo.value)

@patch("faster_whisper.WhisperModel")
@patch("torch.cuda.is_available", return_value=False)
def test_get_model_cpu(mock_cuda, mock_whisper_model):
    from src.transcribe import get_model
    get_model("base")
    mock_whisper_model.assert_called_once_with("base", device="cpu", compute_type="int8")

@patch("faster_whisper.WhisperModel")
@patch("torch.cuda.is_available", return_value=True)
def test_get_model_cuda(mock_cuda, mock_whisper_model):
    from src.transcribe import get_model
    get_model("base")
    mock_whisper_model.assert_called_once_with("base", device="cuda", compute_type="float16")

def test_merge_speakers():
    from src.transcribe import merge_speakers
    whisper_segments = [
        {"start": 0.0, "end": 2.0, "text": "Hello"},
        {"start": 2.0, "end": 4.0, "text": "World"}
    ]
    speaker_segments = [
        {"start": 0.0, "end": 2.5, "speaker": "SPEAKER_00"},
        {"start": 2.5, "end": 4.0, "speaker": "SPEAKER_01"}
    ]

    merged = merge_speakers(whisper_segments, speaker_segments)

    assert merged[0]["speaker"] == "SPEAKER_00"
    assert merged[1]["speaker"] == "SPEAKER_01" # 2.0-4.0 overlaps 0.5s with SPK00 and 1.5s with SPK01

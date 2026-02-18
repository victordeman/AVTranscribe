import pytest
from unittest.mock import MagicMock, patch
import os
from src.transcribe import transcribe_with_whisper, _MODELS

@pytest.fixture(autouse=True)
def clear_models_cache():
    _MODELS.clear()

@patch("whisper.load_model")
@patch("torch.cuda.is_available", return_value=False)
def test_transcribe_with_whisper_success(mock_cuda, mock_load_model):
    # Setup mock model
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "Hello world", "segments": []}
    mock_load_model.return_value = mock_model
    
    # Execute
    result = transcribe_with_whisper("dummy_path.mp3", language="en")
    
    # Assertions
    assert result["text"] == "Hello world"
    mock_load_model.assert_called_once_with("base", device="cpu")
    mock_model.transcribe.assert_called_once_with("dummy_path.mp3", language="en", task="transcribe")

@patch("whisper.load_model")
@patch("torch.cuda.is_available", return_value=False)
def test_transcribe_with_whisper_auto_language(mock_cuda, mock_load_model):
    # Setup mock model
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "Detected language text", "segments": []}
    mock_load_model.return_value = mock_model
    
    # Execute
    result = transcribe_with_whisper("dummy_path.mp3", language="auto")
    
    # Assertions
    assert result["text"] == "Detected language text"
    mock_model.transcribe.assert_called_once_with("dummy_path.mp3", language=None, task="transcribe")

@patch("whisper.load_model")
@patch("torch.cuda.is_available", return_value=True)
def test_transcribe_with_whisper_cuda(mock_cuda, mock_load_model):
    # Setup mock model
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "GPU power", "segments": []}
    mock_load_model.return_value = mock_model
    
    # Execute
    result = transcribe_with_whisper("dummy_path.mp3")
    
    # Assertions
    assert result["text"] == "GPU power"
    mock_load_model.assert_called_once_with("base", device="cuda")

@patch("whisper.load_model")
def test_transcribe_with_whisper_model_caching(mock_load_model):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "cached", "segments": []}
    mock_load_model.return_value = mock_model
    
    # Call twice
    transcribe_with_whisper("path1.mp3")
    transcribe_with_whisper("path2.mp3")
    
    # load_model should only be called once
    mock_load_model.assert_called_once()
    assert mock_model.transcribe.call_count == 2

@patch("whisper.load_model")
def test_transcribe_with_whisper_error(mock_load_model):
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = Exception("Whisper error")
    mock_load_model.return_value = mock_model
    
    with pytest.raises(Exception) as excinfo:
        transcribe_with_whisper("bad_file.mp3")
    
    assert "Whisper error" in str(excinfo.value)

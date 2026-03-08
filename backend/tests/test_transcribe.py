import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# Mock whisper and torch for the entire module if they don't exist
sys.modules['whisper'] = MagicMock()
sys.modules['torch'] = MagicMock()

import src.transcribe
from src.transcribe import transcribe_with_whisper, _MODELS, ProgressStdout, _PROGRESS_CALLBACK

@pytest.fixture(autouse=True)
def clear_models_cache():
    _MODELS.clear()

@patch("src.transcribe.get_model")
def test_transcribe_with_whisper_success(mock_get_model):
    # Setup mock model
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "Hello world", "segments": []}
    mock_get_model.return_value = mock_model
    
    # Execute
    result = transcribe_with_whisper("dummy_path.mp3", language="en")
    
    # Assertions
    assert result["text"] == "Hello world"
    mock_model.transcribe.assert_called_once_with("dummy_path.mp3", language="en", task="transcribe")

@patch("src.transcribe.get_model")
def test_transcribe_with_whisper_on_segment(mock_get_model):
    # Setup mock model
    mock_model = MagicMock()
    
    # Callback
    on_segment = MagicMock()
    
    def mock_transcribe(*args, **kwargs):
        if kwargs.get('verbose'):
            # Manually simulate what ProgressStdout would do
            ProgressStdout(sys.stdout).write("[00:00.000 --> 00:05.000] segment 1\n")
            ProgressStdout(sys.stdout).write("[01:05.000 --> 01:10.000] segment 2\n")
            ProgressStdout(sys.stdout).write("[02:00.000 --> 02:05.000] s3\n[02:05.000 --> 02:10.000] s4\n")
        return {"text": "done", "segments": [{}, {}, {}, {}]}

    mock_model.transcribe.side_effect = mock_transcribe
    mock_get_model.return_value = mock_model
    
    # Execute
    result = transcribe_with_whisper("dummy_path.mp3", on_segment=on_segment)
    
    # Assertions
    assert result["text"] == "done"
    assert on_segment.call_count == 4

@patch("src.transcribe.get_model")
def test_transcribe_with_whisper_error(mock_get_model):
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = Exception("Whisper error")
    mock_get_model.return_value = mock_model
    
    with pytest.raises(Exception) as excinfo:
        transcribe_with_whisper("bad_file.mp3")
    
    assert "Whisper error" in str(excinfo.value)

@patch("whisper.load_model")
@patch("torch.cuda.is_available", return_value=False)
def test_get_model_cpu(mock_cuda, mock_load_model):
    from src.transcribe import get_model
    get_model("base")
    mock_load_model.assert_called_once_with("base", device="cpu")

@patch("whisper.load_model")
@patch("torch.cuda.is_available", return_value=True)
def test_get_model_cuda(mock_cuda, mock_load_model):
    from src.transcribe import get_model
    get_model("base")
    mock_load_model.assert_called_once_with("base", device="cuda")

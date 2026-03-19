import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# Mock modules that are not available in the environment
sys.modules["torch"] = MagicMock()
sys.modules["transformers"] = MagicMock()

from src.transcribe import transcribe_with_whisper, _PIPES, get_pipeline

@pytest.fixture(autouse=True)
def clear_pipes_cache():
    _PIPES.clear()

@patch("src.transcribe.get_pipeline")
@patch("torch.cuda.is_available", return_value=False)
def test_transcribe_with_whisper_hf_local_success(mock_cuda, mock_get_pipeline):
    # Setup mock pipeline
    mock_pipe = MagicMock()
    mock_pipe.return_value = {"text": "Hello world from HF", "chunks": [{"start": 0, "end": 1, "text": "Hello"}]}
    mock_get_pipeline.return_value = mock_pipe
    
    # Execute
    result = transcribe_with_whisper("dummy_path.mp3", language="en")
    
    # Assertions
    assert result["text"] == "Hello world from HF"
    assert len(result["segments"]) == 1
    mock_get_pipeline.assert_called_once()
    mock_pipe.assert_called_once_with("dummy_path.mp3", generate_kwargs={"task": "transcribe", "language": "en"}, return_timestamps=True)

@patch("httpx.post")
@patch("src.transcribe.open", create=True)
@patch.dict(os.environ, {"HF_TOKEN": "test_token"})
def test_transcribe_with_hf_api_success(mock_open, mock_post):
    # Setup mock file
    mock_file = MagicMock()
    mock_file.read.return_value = b"fake data"
    mock_open.return_value.__enter__.return_value = mock_file

    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    # HF API returns 'chunks' when timestamps are requested
    mock_response.json.return_value = {"text": "API Transcription", "chunks": [{"start": 0, "end": 2, "text": "API"}]}
    mock_post.return_value = mock_response
    
    # Execute
    result = transcribe_with_whisper("dummy_path.mp3", language="auto")
    
    # Assertions
    assert result["text"] == "API Transcription"
    assert len(result["segments"]) == 1
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs["params"]["return_timestamps"] == "true"

def test_get_pipeline_caching():
    with patch("transformers.pipeline") as mock_pipeline, \
         patch("transformers.AutoModelForSpeechSeq2Seq.from_pretrained") as mock_model, \
         patch("transformers.AutoProcessor.from_pretrained") as mock_processor:
        
        mock_pipe = MagicMock()
        mock_pipeline.return_value = mock_pipe
        
        # Call get_pipeline twice
        get_pipeline("some-model")
        get_pipeline("some-model")
        
        # Internal transformers.pipeline should only be called once
        mock_pipeline.assert_called_once()

@patch("src.transcribe.get_pipeline")
def test_transcribe_with_whisper_hf_error(mock_get_pipeline):
    mock_pipe = MagicMock()
    mock_pipe.side_effect = Exception("HF error")
    mock_get_pipeline.return_value = mock_pipe
    
    with pytest.raises(Exception) as excinfo:
        transcribe_with_whisper("bad_file.mp3")
    
    assert "HF error" in str(excinfo.value)

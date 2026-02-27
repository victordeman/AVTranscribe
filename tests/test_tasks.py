import pytest
from unittest.mock import MagicMock, patch
from src.tasks import transcribe_task
from src.models import Transcription
import os

@pytest.fixture
def mock_db():
    db = MagicMock()
    return db

@patch("src.tasks.session_scope")
@patch("src.tasks.transcribe_with_whisper")
@patch("src.tasks.clean_to_csv")
@patch("os.path.exists")
@patch("os.remove")
def test_transcribe_task_success(
    mock_remove, mock_exists, mock_clean, mock_transcribe, mock_scope, mock_db
):
    # Setup
    mock_scope.return_value.__enter__.return_value = mock_db
    mock_transcribe.return_value = {"text": "Transcribed text", "segments": [{"start": 0, "end": 1, "text": "Transcribed text"}]}
    mock_clean.return_value = "/tmp/test.csv"
    mock_exists.return_value = True
    
    mock_trans = MagicMock(spec=Transcription)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_trans
    
    # Execute
    task_self = MagicMock()
    task_self.request.retries = 0
    task_self.max_retries = 3
    
    transcribe_task.__wrapped__.__func__(task_self, "dummy.mp3", "en", "auto", "task-123")
    
    # Assertions
    assert mock_trans.status == "done"
    assert mock_trans.text == "Transcribed text"
    assert mock_trans.csv_path == "/tmp/test.csv"
    assert mock_trans.progress == 1
    mock_remove.assert_called_once_with("dummy.mp3")
    mock_transcribe.assert_called_once_with("dummy.mp3", language="en")

@patch("src.tasks.session_scope")
@patch("src.tasks.transcribe_with_whisper")
def test_transcribe_task_missing_record(mock_transcribe, mock_scope, mock_db):
    # Setup
    mock_scope.return_value.__enter__.return_value = mock_db
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    task_self = MagicMock()
    task_self.request.retries = 0
    
    # Execute
    transcribe_task.__wrapped__.__func__(task_self, "dummy.mp3", "en", "auto", "task-123")
    
    # Assertions
    mock_transcribe.assert_not_called()

@patch("src.tasks.session_scope")
@patch("src.tasks.transcribe_with_whisper")
@patch("os.path.exists")
@patch("os.remove")
def test_transcribe_task_failure_retry(
    mock_remove, mock_exists, mock_transcribe, mock_scope, mock_db
):
    # Setup
    mock_scope.return_value.__enter__.return_value = mock_db
    mock_transcribe.side_effect = Exception("Whisper error")
    mock_exists.return_value = True
    
    mock_trans = MagicMock(spec=Transcription)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_trans
    
    task_self = MagicMock()
    task_self.request.retries = 0
    task_self.max_retries = 3
    task_self.retry.side_effect = Exception("Retry called")
    
    # Execute & Assert retry
    with pytest.raises(Exception, match="Retry called"):
        transcribe_task.__wrapped__.__func__(task_self, "dummy.mp3", "en", "auto", "task-123")
    
    assert "retrying" in mock_trans.status
    mock_remove.assert_not_called()

@patch("src.tasks.session_scope")
@patch("src.tasks.transcribe_with_whisper")
@patch("os.path.exists")
@patch("os.remove")
def test_transcribe_task_final_failure(
    mock_remove, mock_exists, mock_transcribe, mock_scope, mock_db
):
    # Setup
    mock_scope.return_value.__enter__.return_value = mock_db
    mock_transcribe.side_effect = Exception("Final error")
    mock_exists.return_value = True
    
    mock_trans = MagicMock(spec=Transcription)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_trans
    
    task_self = MagicMock()
    task_self.request.retries = 3
    task_self.max_retries = 3
    
    # Execute & Assert final failure
    with pytest.raises(Exception, match="Final error"):
        transcribe_task.__wrapped__.__func__(task_self, "dummy.mp3", "en", "auto", "task-123")
    
    assert mock_trans.status == "failed"
    assert "Failed after 3 retries" in mock_trans.error_message
    mock_remove.assert_called_once_with("dummy.mp3")

@patch("os.listdir")
@patch("os.path.getmtime")
@patch("os.remove")
@patch("time.time")
def test_cleanup_temp_files(mock_time, mock_remove, mock_mtime, mock_listdir):
    from src.tasks import cleanup_temp_files
    # Setup
    mock_time.return_value = 100000
    mock_listdir.return_value = ["old.txt", "new.txt", "other.log"]
    
    def getmtime_side_effect(path):
        if "old.txt" in path:
            return 100000 - (25 * 3600)
        return 100000 - (1 * 3600)
    
    mock_mtime.side_effect = getmtime_side_effect
    
    # Execute
    cleanup_temp_files()
    
    # Assertions
    mock_remove.assert_called_once()
    assert "old.txt" in mock_remove.call_args[0][0]

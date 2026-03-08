import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, CheckCircle2, AlertCircle, Clock } from 'lucide-react';
import DownloadButtons from './DownloadButtons';

interface StatusDisplayProps {
  taskId: string;
}

interface TaskStatus {
  status: string;
  progress: number;
  error_message: string | null;
}

const StatusDisplay: React.FC<StatusDisplayProps> = ({ taskId }) => {
  const [task, setTask] = useState<TaskStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await axios.get(`/status/${taskId}`, {
          headers: { 'Accept': 'application/json' }
        });
        setTask(response.data);

        if (response.data.status === 'done' || response.data.status === 'failed') {
          return true;
        }
      } catch (err) {
        console.error('Failed to fetch status:', err);
        setError('Failed to get transcription status.');
        return true;
      }
      return false;
    };

    fetchStatus();
    const interval = window.setInterval(async () => {
      const shouldStop = await fetchStatus();
      if (shouldStop) {
        clearInterval(interval);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [taskId]);

  if (error) {
    return (
      <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200 mt-8">
        <div className="flex items-center space-x-2 text-red-600">
          <AlertCircle className="h-5 w-5" />
          <p className="font-semibold">{error}</p>
        </div>
      </div>
    );
  }

  if (!task) return null;

  const isDone = task.status === 'done';
  const isFailed = task.status === 'failed';
  const isProcessing = task.status === 'processing' || task.status.includes('retrying');

  return (
    <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200 mt-8 transition-all duration-300">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-800">Transcription Status</h3>
        <span className={`px-3 py-1 text-xs font-bold rounded-full uppercase
          ${isDone ? 'bg-green-100 text-green-700' :
            isFailed ? 'bg-red-100 text-red-700' :
            isProcessing ? 'bg-blue-100 text-blue-700' :
            'bg-yellow-100 text-yellow-700'}`}
        >
          {task.status}
        </span>
      </div>

      {isDone ? (
        <div className="space-y-4">
          <div className="p-4 bg-green-50 border border-green-100 rounded-md flex items-center justify-center space-x-2">
            <CheckCircle2 className="h-5 w-5 text-green-500" />
            <p className="text-sm text-green-700 font-medium italic">Transcription complete!</p>
          </div>
          <DownloadButtons taskId={taskId} />
        </div>
      ) : isFailed ? (
        <div className="p-4 bg-red-50 border border-red-100 rounded-md">
          <div className="flex items-center space-x-2 mb-2">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-sm text-red-700 font-semibold">Error occurred</p>
          </div>
          <p className="text-xs text-red-600 mt-1 bg-white p-2 rounded border border-red-100 break-words">
            {task.error_message || "Internal task failure"}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 w-full py-2 px-4 bg-gray-100 text-gray-700 text-sm font-medium rounded hover:bg-gray-200 transition"
          >
            Try Another Upload
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center space-x-3">
            <div className="relative">
              <div className="h-10 w-10 rounded-full border-2 border-indigo-100"></div>
              <Loader2 className="animate-spin h-10 w-10 text-indigo-600 absolute top-0 left-0" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900">
                {task.status === 'processing' ? 'Processing Media' :
                 task.status.includes('retrying') ? 'Retrying Task' : 'In Queue'}
              </p>
              <p className="text-xs text-gray-500">
                {task.status === 'processing' ? `${task.progress} segments transcribed so far...` :
                 task.status.includes('retrying') ? 'Temporarily failed, trying again...' :
                 'Waiting for an available worker...'}
              </p>
            </div>
          </div>

          <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
            <ProgressBar status={task.status} progress={task.progress} />
          </div>

          <p className="text-[10px] text-gray-400 text-center flex items-center justify-center">
            <Clock className="h-3 w-3 mr-1" />
            Do not close this page while processing
          </p>
        </div>
      )}
    </div>
  );
};

const ProgressBar: React.FC<{ status: string, progress: number }> = ({ status, progress }) => {
  let width = 10;
  if (status === 'processing') {
    width = 40 + (progress % 50);
  } else if (status.includes('retrying')) {
    width = 25;
  }

  return (
    <div
      className="bg-indigo-600 h-2.5 rounded-full transition-all duration-1000 ease-out"
      style={{ width: `${width}%` }}
    ></div>
  );
};

export default StatusDisplay;

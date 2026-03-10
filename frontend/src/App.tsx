import { useState, useEffect } from 'react';
import UploadForm from './components/UploadForm';
import StatusDisplay from './components/StatusDisplay';
import { Loader2 } from 'lucide-react';

function App() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [isUploading, setIsUploading] = useState<boolean>(false);

  // Set API base URL if needed (similar to the original HTMX implementation)
  useEffect(() => {
    const apiBase = window.localStorage.getItem('API_BASE_URL');
    if (apiBase) {
      // Axios can be configured globally or via an instance
      // For simplicity in this demo, we assume the same origin or proxy
    }
  }, []);

  const handleUploadStart = (id: string) => {
    setTaskId(id);
    setIsUploading(false);
  };

  const handleUploadProgress = (progress: number) => {
    setIsUploading(true);
    setUploadProgress(progress);
  };

  return (
    <div className="bg-gray-100 min-h-screen font-sans py-12 px-4">
      <div className="container mx-auto">
        <header className="text-center mb-12">
          <h1 className="text-4xl font-extrabold text-indigo-700 mb-2">AVTranscribe</h1>
          <p className="text-gray-600 text-lg">Fast, accurate, and open-source media transcription</p>
        </header>

        <main className="max-w-xl mx-auto">
          <UploadForm
            onUploadStart={handleUploadStart}
            onUploadProgress={handleUploadProgress}
          />

          {isUploading && (
            <div className="w-full mt-6 bg-indigo-50 rounded-lg p-4 border border-indigo-100">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-indigo-700 uppercase">
                  {uploadProgress >= 100 ? 'Finalizing upload...' : `Uploading: ${uploadProgress}%`}
                </span>
                <Loader2 className="animate-spin h-4 w-4 text-indigo-600" />
              </div>
              <div className="w-full bg-indigo-200 rounded-full h-1.5">
                <div
                  className="bg-indigo-600 h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
            </div>
          )}

          {taskId && <StatusDisplay taskId={taskId} />}
        </main>

        <footer className="mt-16 text-center text-gray-600 text-sm">
          <p>&copy; 2024 AVTranscribe. Powered by FastAPI, Celery, and Whisper.</p>
        </footer>
      </div>
    </div>
  );
}

export default App;

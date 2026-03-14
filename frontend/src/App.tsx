import { useState, useEffect } from 'react';
import UploadForm from './components/UploadForm';
import StatusDisplay from './components/StatusDisplay';
import { Loader2 } from 'lucide-react';

import Auth from './components/Auth';
import axios from 'axios';

function App() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadEta, setUploadEta] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!localStorage.getItem('token'));

  // Set up axios interceptors for JWT and error handling
  useEffect(() => {
    const requestInterceptor = axios.interceptors.request.use((config) => {
      const token = localStorage.getItem('token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    const responseInterceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response && error.response.status === 401) {
          localStorage.removeItem('token');
          setIsAuthenticated(false);
          setTaskId(null);
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.request.eject(requestInterceptor);
      axios.interceptors.response.eject(responseInterceptor);
    };
  }, []);

  const handleUploadStart = (id: string) => {
    setTaskId(id);
    setIsUploading(false);
  };

  const handleUploadProgress = (progress: number, total?: number) => {
    setIsUploading(true);
    setUploadProgress(progress);

    if (total) {
      const fileSizeMB = total / (1024 * 1024);
      const estMediaDurationMin = fileSizeMB;
      const estProcessTimeSec = estMediaDurationMin * 60 / 5;

      if (estProcessTimeSec < 60) {
        setUploadEta('< 1 min');
      } else {
        setUploadEta(`~${Math.round(estProcessTimeSec / 60)} min`);
      }
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsAuthenticated(false);
    setTaskId(null);
  };

  return (
    <div className="bg-gray-100 min-h-screen font-sans py-12 px-4">
      <div className="container mx-auto">
        <header className="text-center mb-12">
          <h1 className="text-4xl font-extrabold text-indigo-700 mb-2">AVTranscribe</h1>
          <p className="text-gray-600 text-lg">Fast, accurate, and open-source media transcription</p>
        </header>

        <main className="max-w-xl mx-auto">
          {!isAuthenticated ? (
            <Auth onLoginSuccess={() => setIsAuthenticated(true)} />
          ) : (
            <>
              <div className="flex justify-end mb-4">
                <button onClick={handleLogout} className="text-sm text-gray-500 hover:text-red-600">Logout</button>
              </div>
              <UploadForm
                onUploadStart={handleUploadStart}
                onUploadProgress={handleUploadProgress}
              />

              {isUploading && (
                <div className="w-full mt-6 bg-indigo-50 rounded-lg p-4 border border-indigo-100">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-indigo-700 uppercase">
                        {uploadProgress >= 100 ? 'Finalizing upload...' : `Uploading: ${uploadProgress}%`}
                      </span>
                      {uploadEta && (
                        <span className="text-[10px] text-indigo-500 mt-1">
                          Est. transcription time: {uploadEta}
                        </span>
                      )}
                    </div>
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
            </>
          )}
        </main>

        <footer className="mt-16 text-center text-gray-600 text-sm">
          <p>&copy; 2024 AVTranscribe. Powered by FastAPI, Celery, and Whisper.</p>
        </footer>
      </div>
    </div>
  );
}

export default App;

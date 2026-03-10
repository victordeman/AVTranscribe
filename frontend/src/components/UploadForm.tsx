import React, { useState } from 'react';
import axios from 'axios';
import { Upload, Loader2 } from 'lucide-react';

interface UploadFormProps {
  onUploadStart: (taskId: string) => void;
  onUploadProgress: (progress: number) => void;
}

const UploadForm: React.FC<UploadFormProps> = ({ onUploadStart, onUploadProgress }) => {
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState('auto');
  const [format, setFormat] = useState('auto');
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('language', language);
    formData.append('format', format);

    try {
      const response = await axios.post('/transcribe', formData, {
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            onUploadProgress(percentCompleted);
          }
        },
      });

      onUploadStart(response.data.task_id);
    } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
      console.error('Upload failed:', err);
      setError(err.response?.data?.detail || 'Failed to upload file. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden p-8 border border-gray-200">
      <h2 id="upload-form-title" className="text-2xl font-semibold text-gray-800 mb-6 border-b border-gray-100 pb-2">Upload Media</h2>

      <form onSubmit={handleSubmit} aria-labelledby="upload-form-title" className="space-y-6">
        <div>
          <label htmlFor="file" className="block text-sm font-medium text-gray-700 mb-1">
            Select File (Audio or Video)
          </label>
          <div className="relative">
            <input
              type="file"
              name="file"
              id="file"
              required
              aria-describedby="file-input-help"
              onChange={handleFileChange}
              disabled={isUploading}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded-md file:border-0
                file:text-sm file:font-semibold
                file:bg-indigo-50 file:text-indigo-700
                hover:file:bg-indigo-100 cursor-pointer transition-all disabled:opacity-50"
            />
          </div>
          <p id="file-input-help" className="mt-1 text-xs text-gray-600">Supported formats: mp3, wav, mp4, mkv, etc. Max 100MB.</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="language" className="block text-sm font-medium text-gray-700 mb-1">Language</label>
            <select
              name="language"
              id="language"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              disabled={isUploading}
              className="block w-full mt-1 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2.5 bg-gray-50 disabled:opacity-50"
            >
              <option value="auto">Auto-detect</option>
              <option value="en">English</option>
              <option value="es">Spanish</option>
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="it">Italian</option>
              <option value="pt">Portuguese</option>
              <option value="nl">Dutch</option>
              <option value="ru">Russian</option>
              <option value="zh">Chinese</option>
              <option value="ja">Japanese</option>
              <option value="ko">Korean</option>
            </select>
          </div>

          <div>
            <label htmlFor="format" className="block text-sm font-medium text-gray-700 mb-1">Media Format</label>
            <select
              name="format"
              id="format"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              disabled={isUploading}
              className="block w-full mt-1 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2.5 bg-gray-50 disabled:opacity-50"
            >
              <option value="auto">Auto</option>
              <option value="audio">Audio Only</option>
              <option value="video">Video</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-100 rounded-md text-red-600 text-sm">
            {error}
          </div>
        )}

        <div className="pt-4">
          <button
            type="submit"
            disabled={!file || isUploading}
            className="w-full flex justify-center items-center py-3 px-4 border border-transparent rounded-md shadow-sm text-base font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUploading ? (
              <>
                <Loader2 className="animate-spin -ml-1 mr-2 h-5 w-5" aria-hidden="true" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="-ml-1 mr-2 h-5 w-5" aria-hidden="true" />
                Transcribe Now
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default UploadForm;

import React from 'react';
import { FileText, Table } from 'lucide-react';

interface DownloadButtonsProps {
  taskId: string;
}

const DownloadButtons: React.FC<DownloadButtonsProps> = ({ taskId }) => {
  return (
    <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-3">
      <a
        href={`/download/${taskId}/text`}
        className="flex-1 flex items-center justify-center py-2.5 px-4 bg-indigo-600 text-white font-semibold rounded-md hover:bg-indigo-700 transition shadow-sm"
      >
        <FileText className="h-4 w-4 mr-2" />
        Download TXT
      </a>
      <a
        href={`/download/${taskId}/csv`}
        className="flex-1 flex items-center justify-center py-2.5 px-4 bg-white text-indigo-700 border border-indigo-200 font-semibold rounded-md hover:bg-indigo-50 transition shadow-sm"
      >
        <Table className="h-4 w-4 mr-2" />
        Download CSV
      </a>
    </div>
  );
};

export default DownloadButtons;

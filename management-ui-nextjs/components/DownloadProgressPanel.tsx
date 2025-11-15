'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { FileDownloadState, ModelDownloadState } from '@/lib/downloadState';

interface DownloadProgressPanelProps {
  modelId: string;
  modelName: string;
  downloadState: ModelDownloadState;
  onCancelFile: (modelId: string, fileName: string) => void;
  onCancelAll: (modelId: string) => void;
}

export default function DownloadProgressPanel({
  modelId,
  modelName,
  downloadState,
  onCancelFile,
  onCancelAll
}: DownloadProgressPanelProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="bg-gradient-to-br from-gray-800/90 to-gray-900/90 rounded-xl p-6 border border-white/10 shadow-xl mb-6"
    >
      {/* Model Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-aipg-orange animate-pulse" />
          <div>
            <h3 className="font-bold text-white text-lg">{modelName}</h3>
            <p className="text-sm text-gray-400">
              {downloadState.completed_files} of {downloadState.total_files} files complete
            </p>
          </div>
        </div>
        <button
          onClick={() => onCancelAll(modelId)}
          className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-bold rounded-lg transition-all"
        >
          Cancel All
        </button>
      </div>

      {/* Overall Progress Bar */}
      <div className="mb-6">
        <div className="flex justify-between text-xs text-gray-400 mb-2">
          <span>Overall Progress</span>
          <span>{downloadState.progress.toFixed(1)}%</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-3">
          <div
            className="bg-gradient-to-r from-aipg-orange to-aipg-gold h-3 rounded-full transition-all duration-300"
            style={{ width: `${downloadState.progress}%` }}
          />
        </div>
        {downloadState.speed && downloadState.eta && (
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>{downloadState.speed}</span>
            <span>ETA: {downloadState.eta}</span>
          </div>
        )}
      </div>

      {/* Individual Files */}
      <div className="space-y-3">
        <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">Files</h4>
        <AnimatePresence>
          {downloadState.files.map((file, index) => (
            <motion.div
              key={file.file_name}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ delay: index * 0.05 }}
              className="bg-gray-800/50 rounded-lg p-4 border border-white/5"
            >
              {/* File Header */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  {/* Status Indicator */}
                  <div className={`w-3 h-3 rounded-full flex-shrink-0 ${
                    file.status === 'completed' ? 'bg-green-500' :
                    file.status === 'downloading' ? 'bg-aipg-orange animate-pulse' :
                    file.status === 'error' ? 'bg-red-500' :
                    file.status === 'cancelled' ? 'bg-yellow-500' :
                    'bg-gray-500'
                  }`} />
                  
                  {/* File Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-white text-sm truncate">
                        {file.file_name}
                      </p>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-aipg-gold/20 text-aipg-gold flex-shrink-0">
                        {file.file_type}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500">
                      {file.file_size_mb > 0 ? `${file.file_size_mb.toFixed(2)} MB` : 'Size unknown'}
                    </p>
                  </div>
                </div>

                {/* Cancel Button */}
                {(file.status === 'queued' || file.status === 'downloading') && (
                  <button
                    onClick={() => onCancelFile(modelId, file.file_name)}
                    className="px-3 py-1 bg-red-600/80 hover:bg-red-600 text-white text-xs font-bold rounded transition-all flex-shrink-0"
                    title="Cancel this file"
                  >
                    ✕
                  </button>
                )}
              </div>

              {/* Progress Bar */}
              {(file.status === 'downloading' || file.status === 'queued') && (
                <div className="mt-3">
                  <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span>
                      {file.status === 'queued' ? 'Queued' : 
                       file.downloaded_mb > 0 ? `${file.downloaded_mb.toFixed(2)} MB downloaded` : 'Starting...'}
                    </span>
                    <span>{file.progress.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all duration-300 ${
                        file.status === 'downloading' 
                          ? 'bg-gradient-to-r from-aipg-orange to-aipg-gold'
                          : 'bg-gray-600'
                      }`}
                      style={{ width: `${file.progress}%` }}
                    />
                  </div>
                  {file.speed && file.eta && file.status === 'downloading' && (
                    <div className="flex justify-between text-xs text-gray-500 mt-1">
                      <span>{file.speed}</span>
                      <span>ETA: {file.eta}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Completed Status */}
              {file.status === 'completed' && (
                <div className="mt-2 flex items-center gap-2 text-green-400 text-xs">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  <span>Download complete</span>
                </div>
              )}

              {/* Error Status */}
              {file.status === 'error' && (
                <div className="mt-2 flex items-center gap-2 text-red-400 text-xs">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <span>{file.error_message || 'Download failed'}</span>
                </div>
              )}

              {/* Cancelled Status */}
              {file.status === 'cancelled' && (
                <div className="mt-2 flex items-center gap-2 text-yellow-400 text-xs">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <span>Cancelled</span>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Message */}
      {downloadState.message && (
        <div className="mt-4 px-4 py-2 bg-gray-700/50 rounded-lg text-sm text-gray-300">
          {downloadState.message}
        </div>
      )}
    </motion.div>
  );
}


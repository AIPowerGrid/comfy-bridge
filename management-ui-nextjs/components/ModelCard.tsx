'use client';

import { motion } from 'framer-motion';

interface ModelCardProps {
  modelName: string;
  model: any;
  isSelected: boolean;
  isCompatible: boolean;
  isHosting: boolean;
  isDownloading?: boolean;
  downloadProgress?: number;
  onToggle: () => void;
  onUninstall?: () => void;
  onHost?: () => void;
  onUnhost?: () => void;
  onDownload?: () => void;
  onDownloadAndHost?: () => void;
  onCancelDownload?: () => void;
  index: number;
}

export default function ModelCard({
  modelName,
  model,
  isSelected,
  isCompatible,
  isHosting,
  isDownloading = false,
  downloadProgress = 0,
  onToggle,
  onUninstall,
  onHost,
  onUnhost,
  onDownload,
  onDownloadAndHost,
  onCancelDownload,
  index,
}: ModelCardProps) {
  const handleClick = (e: React.MouseEvent) => {
    // Don't toggle if clicking the uninstall button
    if ((e.target as HTMLElement).closest('button')) {
      return;
    }
    if (isCompatible && !model.installed) {
      onToggle();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      onClick={handleClick}
      className={`relative overflow-hidden rounded-xl p-5 transition-all duration-300 ${
        model.installed
          ? 'bg-gradient-to-br from-blue-500/30 to-purple-500/30 border-2 border-blue-500 shadow-lg shadow-blue-500/50 cursor-default'
          : isSelected
          ? 'bg-gradient-to-br from-aipg-orange/30 to-aipg-gold/30 border-2 border-aipg-orange shadow-lg shadow-aipg-orange/50 cursor-pointer'
          : 'bg-aipg-darkGray border border-white/10 hover:border-aipg-orange/50 cursor-pointer'
      } ${!isCompatible && !model.installed ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {/* Background glow effect */}
      {isSelected && (
        <div className="absolute inset-0 bg-gradient-to-br from-aipg-orange/20 to-aipg-gold/20 blur-xl"></div>
      )}

      <div className="relative z-10 flex flex-col h-full">
            {/* Header */}
            <div className="mb-3">
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-lg font-bold text-white pr-2 line-clamp-2 flex-1">
                  {model.display_name}
                </h3>
                {isSelected && !model.installed && (
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-aipg-orange flex items-center justify-center ml-2">
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
              </div>
              
              {/* Status pills - separate row to prevent overlap */}
              <div className="flex gap-2 flex-wrap">
                {model.installed && (
              <span className="flex-shrink-0 px-2 py-1 text-xs font-semibold bg-blue-500/20 text-blue-400 rounded-full border border-blue-500/50">
                📁 Installed
              </span>
            )}
            {isHosting && (
              <span className="flex-shrink-0 px-2 py-1 text-xs font-semibold bg-green-500/20 text-green-400 rounded-full border border-green-500/50">
                💰 Earning
              </span>
            )}
            {isDownloading && (
              <span className="flex-shrink-0 px-2 py-1 text-xs font-semibold bg-yellow-500/20 text-yellow-400 rounded-full border border-yellow-500/50">
                ⬇️ Downloading...
              </span>
            )}
                {!isCompatible && !model.installed && !isDownloading && (
                  <span className="flex-shrink-0 px-2 py-1 text-xs font-semibold bg-red-500/20 text-red-400 rounded-full border border-red-500/50">
                    Incompatible
                  </span>
                )}
              </div>
            </div>

        {/* Badges: Capability Type, Style, API Key Requirements */}
        <div className="flex flex-wrap gap-2 mb-2">
          {model.capability_type && (
            <span className="px-2 py-1 text-xs font-bold bg-gradient-to-r from-aipg-orange to-aipg-gold text-white rounded-full border border-aipg-orange/50">
              {model.capability_type}
            </span>
          )}
          {model.style && (
            <span className="px-2 py-1 text-xs font-semibold bg-aipg-gold/20 text-aipg-gold rounded-full border border-aipg-gold/30">
              {model.style}
            </span>
          )}
          {model.requires_civitai_key && (
            <span className="px-2 py-1 text-xs font-semibold bg-purple-500/20 text-purple-400 rounded-full border border-purple-500/50" title="Requires Civitai API Key">
              🔑 Civitai
            </span>
          )}
          {model.requires_huggingface_key && (
            <span className="px-2 py-1 text-xs font-semibold bg-yellow-500/20 text-yellow-400 rounded-full border border-yellow-500/50" title="Requires HuggingFace API Key">
              🔑 HuggingFace
            </span>
          )}
        </div>

            {/* Description */}
            <p className="text-sm text-gray-400 mb-4 line-clamp-2 flex-grow">
              {model.description}
            </p>

            {/* Download Progress Bar */}
            {isDownloading && (
              <div className="mb-4">
                <div className="flex justify-between text-xs text-gray-400 mb-1">
                  <span>Downloading...</span>
                  <span>{downloadProgress.toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div 
                    className="bg-gradient-to-r from-aipg-orange to-aipg-gold h-2 rounded-full transition-all duration-300"
                    style={{ width: `${downloadProgress}%` }}
                  ></div>
                </div>
              </div>
            )}

            {/* Model Stats - Fixed to bottom with same padding as buttons */}
            <div className="flex justify-between pt-4 border-t border-white/10">
              <div className="text-center">
                <div className="text-xs text-gray-500 uppercase mb-1">Size on Disk</div>
                <div className="text-sm font-bold text-white flex items-center justify-center gap-1">
                  {model.size_gb > 0 ? (
                    `${model.size_gb} GB`
                  ) : (
                    <div className="flex items-center gap-1" title="Size data not retrievable from source">
                      <span>Unknown</span>
                      <svg 
                        className="w-4 h-4 text-yellow-400" 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                      </svg>
                    </div>
                  )}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-gray-500 uppercase mb-1">Memory</div>
                <div className="text-sm font-bold text-aipg-gold">{model.vram_required_gb} GB</div>
              </div>
              <div className="text-center">
                <div className="text-xs text-gray-500 uppercase mb-1">Style</div>
                <div className="text-sm font-bold text-white capitalize">{model.style}</div>
              </div>
            </div>

        {/* Action Buttons - Always at bottom */}
        <div className="flex gap-2 pt-4 border-t border-white/10">
          {isDownloading ? (
            /* Downloading: Show cancel button */
            <button
              onClick={(e) => {
                e.stopPropagation();
                onCancelDownload?.();
              }}
              className="flex-1 px-3 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-bold rounded-lg transition-all transform hover:scale-[1.02] flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Cancel Download
            </button>
          ) : model.installed ? (
            /* Downloaded models: Start/Stop Hosting + Remove */
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  isHosting ? onUnhost?.() : onHost?.();
                }}
                className={`flex-1 px-3 py-2 text-white text-sm font-bold rounded-lg transition-all transform hover:scale-[1.02] ${
                  isHosting 
                    ? 'bg-yellow-600 hover:bg-yellow-700' 
                    : 'bg-green-600 hover:bg-green-700'
                }`}
              >
{isHosting ? 'Stop Earning' : 'Start Earning'}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onUninstall?.();
                }}
                className="flex-1 px-3 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-bold rounded-lg transition-all transform hover:scale-[1.02]"
              >
                Remove
              </button>
            </>
          ) : isHosting ? (
            /* Hosting but not downloaded: Must download first, then will auto-host */
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDownloadAndHost?.();
                }}
                className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-bold rounded-lg transition-all transform hover:scale-[1.02]"
              >
                Install & Start Earning
              </button>
          ) : (
            /* Not downloaded, not hosting: Give user choice */
            <>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDownload?.();
                    }}
                    className="flex-1 px-3 py-2 bg-gradient-to-r from-aipg-orange to-orange-600 hover:from-orange-600 hover:to-aipg-orange text-white text-sm font-bold rounded-lg transition-all transform hover:scale-[1.02]"
                  >
                    Install Only
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDownloadAndHost?.();
                    }}
                    className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-bold rounded-lg transition-all transform hover:scale-[1.02]"
                  >
                    Install & Start Earning
                  </button>
            </>
          )}
        </div>
      </div>
    </motion.div>
  );
}


'use client';

import { useState } from 'react';
import { useWallet, useModelVault } from '@/lib/web3';
import { ModelType } from '@/lib/web3/types';
import { motion, AnimatePresence } from 'framer-motion';

const MODEL_TYPE_LABELS: Record<number, string> = {
  [ModelType.SD15]: 'SD 1.5',
  [ModelType.SDXL]: 'SDXL',
  [ModelType.VIDEO]: 'Video',
  [ModelType.FLUX]: 'Flux',
  [ModelType.OTHER]: 'Other',
};

const MODEL_TYPE_COLORS: Record<number, string> = {
  [ModelType.SD15]: 'bg-green-500/20 text-green-300 border-green-500/30',
  [ModelType.SDXL]: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  [ModelType.VIDEO]: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  [ModelType.FLUX]: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  [ModelType.OTHER]: 'bg-gray-500/20 text-gray-300 border-gray-500/30',
};

export function ModelVaultStatus() {
  const { isConnected } = useWallet();
  const { isLoading, error, modelsWithDetails, refreshModels } = useModelVault();
  const [isExpanded, setIsExpanded] = useState(true);

  if (!isConnected) {
    return (
      <div className="bg-gray-900/50 border border-gray-700 rounded-xl p-4">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 bg-gray-500 rounded-full" />
          <div>
            <h3 className="text-sm font-semibold text-gray-300">ModelVault Registry</h3>
            <p className="text-xs text-gray-500">Connect wallet to view on-chain registered models</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-br from-blue-900/20 via-purple-900/20 to-indigo-900/20 border border-blue-500/30 rounded-xl overflow-hidden"
    >
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className={`w-3 h-3 rounded-full ${isLoading ? 'bg-yellow-500 animate-pulse' : error ? 'bg-red-500' : 'bg-green-500'}`} />
            <div className={`absolute inset-0 w-3 h-3 rounded-full ${isLoading ? 'bg-yellow-500' : 'bg-green-500'} animate-ping opacity-30`} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              ModelVault Registry
              <span className="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-300 rounded-full">
                Base Sepolia
              </span>
            </h3>
            <p className="text-xs text-gray-400">
              {isLoading
                ? 'Loading on-chain models...'
                : error
                ? error
                : `${modelsWithDetails.length} models registered on-chain`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              refreshModels();
            }}
            disabled={isLoading}
            className="px-3 py-1.5 bg-blue-600/50 hover:bg-blue-600 text-white text-xs rounded-lg transition-all disabled:opacity-50"
          >
            {isLoading ? 'Syncing...' : 'Sync'}
          </button>
          <svg
            className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      <AnimatePresence>
        {isExpanded && modelsWithDetails.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-gray-700/50"
          >
            <div className="p-4 max-h-96 overflow-y-auto">
              <div className="grid gap-2">
                {modelsWithDetails.map(({ hash, info }, i) => (
                  <motion.div
                    key={hash}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="bg-gray-800/50 rounded-lg p-3 border border-gray-700/50 hover:border-gray-600 transition-colors"
                  >
                    {info ? (
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <h4 className="text-sm font-medium text-white truncate">
                              {info.displayName || info.fileName}
                            </h4>
                            {info.isNSFW && (
                              <span className="px-1.5 py-0.5 bg-red-500/20 text-red-300 text-xs rounded">
                                NSFW
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-400 truncate mb-2">
                            {info.fileName}
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            <span className={`px-2 py-0.5 text-xs rounded border ${MODEL_TYPE_COLORS[info.modelType] || MODEL_TYPE_COLORS[ModelType.OTHER]}`}>
                              {MODEL_TYPE_LABELS[info.modelType] || 'Unknown'}
                            </span>
                            {info.baseModel && (
                              <span className="px-2 py-0.5 bg-gray-600/50 text-gray-300 text-xs rounded">
                                {info.baseModel}
                              </span>
                            )}
                            {info.inpainting && (
                              <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-300 text-xs rounded">
                                Inpainting
                              </span>
                            )}
                            {info.img2img && (
                              <span className="px-2 py-0.5 bg-teal-500/20 text-teal-300 text-xs rounded">
                                Img2Img
                              </span>
                            )}
                            {info.lora && (
                              <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-300 text-xs rounded">
                                LoRA
                              </span>
                            )}
                            {info.isActive && (
                              <span className="px-2 py-0.5 bg-green-500/20 text-green-300 text-xs rounded">
                                Active
                              </span>
                            )}
                          </div>
                          {info.description && (
                            <p className="text-xs text-gray-500 mt-2 line-clamp-2">
                              {info.description}
                            </p>
                          )}
                        </div>
                        <div className="text-right flex-shrink-0">
                          {info.sizeBytes > 0 && (
                            <p className="text-xs text-gray-400">
                              {(Number(info.sizeBytes) / 1024 / 1024 / 1024).toFixed(2)} GB
                            </p>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between">
                        <p className="text-xs text-gray-500 font-mono truncate">
                          {hash}
                        </p>
                        <span className="text-xs text-gray-600">No details</span>
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {isExpanded && modelsWithDetails.length === 0 && !isLoading && (
        <div className="border-t border-gray-700/50 p-4">
          <p className="text-center text-sm text-gray-500">
            No models registered on-chain yet
          </p>
        </div>
      )}
    </motion.div>
  );
}

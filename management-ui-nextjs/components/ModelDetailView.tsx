'use client';

import { motion } from 'framer-motion';
import { useState } from 'react';

interface ModelDetailViewProps {
  catalog: any;
  diskSpace: any;
  filter: 'all' | 'compatible' | 'selected';
  styleFilter: 'all' | 'text-to-image' | 'text-to-video' | 'image-to-video' | 'image-to-image' | 'anime' | 'realistic' | 'generalist' | 'artistic' | 'video';
  gpuInfo: any;
  onFilterChange: (filter: 'all' | 'compatible' | 'selected') => void;
  onStyleFilterChange: (styleFilter: 'all' | 'text-to-image' | 'text-to-video' | 'image-to-video' | 'image-to-image' | 'anime' | 'realistic' | 'generalist' | 'artistic' | 'video') => void;
  onUninstall: (modelId: string) => void;
  onHost: (modelId: string) => void;
  onUnhost: (modelId: string) => void;
  onDownload: (modelId: string) => void;
  onDownloadAndHost: (modelId: string) => void;
}

interface ConfirmationModalProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  modelName: string;
}

function ConfirmationModal({ isOpen, onConfirm, onCancel, modelName }: ConfirmationModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-gray-900 rounded-xl p-6 border border-gray-700 max-w-md w-full mx-4"
      >
        <h3 className="text-xl font-bold text-white mb-4">Confirm Uninstall</h3>
        <p className="text-gray-300 mb-6">
          Are you sure you want to uninstall <span className="font-semibold text-aipg-orange">{modelName}</span>? 
          This will delete all associated files and cannot be undone.
        </p>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            Yes, Uninstall
          </button>
        </div>
      </motion.div>
    </div>
  );
}

export default function ModelDetailView({
  catalog,
  diskSpace,
  filter,
  styleFilter,
  gpuInfo,
  onFilterChange,
  onStyleFilterChange,
  onUninstall,
  onHost,
  onUnhost,
  onDownload,
  onDownloadAndHost,
}: ModelDetailViewProps) {
  const [confirmModal, setConfirmModal] = useState<{ isOpen: boolean; modelName: string }>({ isOpen: false, modelName: '' });
  const [downloadingModels, setDownloadingModels] = useState<Set<string>>(new Set());
  const [downloadProgress, setDownloadProgress] = useState<{ [key: string]: { progress: number; message: string; speed?: string; eta?: string } }>({});

  const models = catalog?.models || [];
  
  const filteredModels = models.filter((model: any) => {
    // Apply capability filter
    if (filter === 'compatible') {
      const maxVram = gpuInfo?.gpus?.[0]?.vram_available_gb || gpuInfo?.total_memory_gb || 0;
      return model.vram_required_gb <= maxVram;
    }
    
    // Apply style filter
    if (styleFilter !== 'all') {
      if (styleFilter === 'text-to-image' && model.capability_type !== 'Text-to-Image') return false;
      if (styleFilter === 'text-to-video' && model.capability_type !== 'Text-to-Video') return false;
      if (styleFilter === 'image-to-video' && model.capability_type !== 'Image-to-Video') return false;
      if (styleFilter === 'image-to-image' && model.capability_type !== 'Image-to-Image') return false;
      if (styleFilter === 'anime' && model.style !== 'anime') return false;
      if (styleFilter === 'realistic' && model.style !== 'realistic') return false;
      if (styleFilter === 'generalist' && model.style !== 'generalist') return false;
      if (styleFilter === 'artistic' && model.style !== 'artistic') return false;
      if (styleFilter === 'video' && model.style !== 'video') return false;
    }
    
    return true;
  });

  const handleUninstall = (modelId: string) => {
    setConfirmModal({ isOpen: true, modelName: modelId });
  };

  const confirmUninstall = () => {
    onUninstall(confirmModal.modelName);
    setConfirmModal({ isOpen: false, modelName: '' });
  };

  const handleDownload = async (modelId: string) => {
    setDownloadingModels(prev => new Set(prev).add(modelId));
    setDownloadProgress(prev => ({ ...prev, [modelId]: { progress: 0, message: 'Starting download...' } }));
    
    try {
      const response = await fetch('/api/models/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models: [modelId] }),
      });

      if (!response.ok) {
        throw new Error('Download request failed');
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'progress') {
                // Parse progress from message like "[ 12.5%] 2.8 GB/22.2 GB (43.7 MB/s) ETA: 7m34s"
                const progressMatch = data.message.match(/\[\s*(\d+\.?\d*)%\]/);
                const speedMatch = data.message.match(/\(([^)]+)\/s\)/);
                const etaMatch = data.message.match(/ETA:\s*([^)]+)/);
                
                if (progressMatch) {
                  const progress = parseFloat(progressMatch[1]);
                  setDownloadProgress(prev => ({
                    ...prev,
                    [modelId]: {
                      progress,
                      message: data.message,
                      speed: speedMatch?.[1],
                      eta: etaMatch?.[1]
                    }
                  }));
                }
              } else if (data.type === 'complete') {
                if (data.success) {
                  await onDownloadAndHost(modelId);
                } else {
                  throw new Error(data.message);
                }
              } else if (data.type === 'error') {
                throw new Error(data.message);
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Download error:', error);
      setDownloadProgress(prev => ({
        ...prev,
        [modelId]: { progress: 0, message: `Error: ${error instanceof Error ? error.message : 'Unknown error'}` }
      }));
    } finally {
      setDownloadingModels(prev => {
        const newSet = new Set(prev);
        newSet.delete(modelId);
        return newSet;
      });
      setDownloadProgress(prev => {
        const newProgress = { ...prev };
        delete newProgress[modelId];
        return newProgress;
      });
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="glass-effect rounded-xl p-6 border border-white/10"
    >
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <svg className="w-6 h-6 text-aipg-orange" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
          Available Models
        </h2>
        {catalog && (
          <div className="text-sm text-gray-400">
            <span className="font-semibold text-aipg-gold">{catalog.total_count}</span> models available
            {catalog.installed_count > 0 && (
              <span className="ml-3">
                • <span className="font-semibold text-blue-400">{catalog.installed_count}</span> installed
              </span>
            )}
          </div>
        )}
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {[
          { key: 'compatible', label: 'Supported', icon: '✅' },
          { key: 'all', label: 'All Models', icon: '🎯' },
        ].map(({ key, label, icon }) => (
          <button
            key={key}
            onClick={() => onFilterChange(key as any)}
            className={`flex items-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
              filter === key
                ? 'bg-aipg-orange text-white shadow-lg shadow-aipg-orange/30'
                : 'bg-gray-800 text-gray-300 hover:text-white border border-gray-600 hover:border-aipg-orange/50'
            }`}
          >
            <span>{icon}</span>
            {label}
          </button>
        ))}
      </div>

      {/* Content Type Filters */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-400 mb-3">Filter by Content Type:</h3>
        <div className="flex gap-2 flex-wrap">
          {[
            { key: 'all', label: 'All Types', icon: '🎨' },
            { key: 'text-to-image', label: 'Text → Image', icon: '🖼️' },
            { key: 'text-to-video', label: 'Text → Video', icon: '🎬' },
            { key: 'image-to-video', label: 'Image → Video', icon: '🎭' },
            { key: 'image-to-image', label: 'Image → Image', icon: '🔄' },
          ].map(({ key, label, icon }) => (
            <button
              key={key}
              onClick={() => onStyleFilterChange(key as any)}
              className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-all ${
                styleFilter === key
                  ? 'bg-aipg-orange text-white shadow-lg shadow-aipg-orange/30'
                  : 'bg-gray-800 text-gray-300 hover:text-white border border-gray-600 hover:border-aipg-orange/50'
              }`}
            >
              <span>{icon}</span>
              {label}
            </button>
          ))}
        </div>
      </div>

        {/* Windows Explorer Style Table */}
        <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
          {/* Table Header */}
          <div className="bg-gray-800 px-4 py-3 border-b border-gray-700">
            <div className="grid grid-cols-12 gap-2 text-sm font-semibold text-gray-300">
              <div className="col-span-4">Name</div>
              <div className="col-span-2">Type</div>
              <div className="col-span-1">Size</div>
              <div className="col-span-1">VRAM</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-2">Actions</div>
            </div>
          </div>

        {/* Table Body */}
        <div className="divide-y divide-gray-700">
          {filteredModels.map((model: any, index: number) => {
            const maxVram = gpuInfo?.gpus?.[0]?.vram_available_gb || gpuInfo?.total_memory_gb || 0;
            const isCompatible = model.vram_required_gb <= maxVram;
            const isHosting = model.hosting || false;
            const isDownloading = downloadingModels.has(model.id);

            return (
              <motion.div
                key={model.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="px-4 py-3 hover:bg-gray-800/50 transition-colors"
              >
                <div className="grid grid-cols-12 gap-2 items-center text-sm">
                  {/* Name */}
                  <div className="col-span-4">
                    <div className="font-medium text-white">{model.display_name}</div>
                    <div className="text-xs text-gray-400 line-clamp-1">{model.description}</div>
                  </div>

                  {/* Type */}
                  <div className="col-span-2">
                    <div className="text-gray-300">{model.capability_type}</div>
                    <div className="text-xs text-gray-500">{model.style}</div>
                  </div>

                  {/* Size */}
                  <div className="col-span-1">
                    <div className="text-gray-300">
                      {model.size_gb > 0 ? `${model.size_gb} GB` : 'Unknown'}
                    </div>
                  </div>

                  {/* VRAM */}
                  <div className="col-span-1">
                    <div className={`${isCompatible ? 'text-gray-300' : 'text-red-400'}`}>
                      {model.vram_required_gb} GB
                    </div>
                  </div>

                  {/* Status */}
                  <div className="col-span-2">
                    <div className="flex flex-wrap gap-1">
                      {model.installed && (
                        <span className="px-2 py-1 text-xs bg-blue-500/20 text-blue-400 rounded border border-blue-500/50">
                          Installed
                        </span>
                      )}
                      {isHosting && (
                        <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded border border-green-500/50">
                          Earning
                        </span>
                      )}
                      {isDownloading && (
                        <span className="px-2 py-1 text-xs bg-yellow-500/20 text-yellow-400 rounded border border-yellow-500/50">
                          Downloading...
                        </span>
                      )}
                      {!isCompatible && !model.installed && (
                        <span className="px-2 py-1 text-xs bg-red-500/20 text-red-400 rounded border border-red-500/50">
                          Incompatible
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="col-span-2">
                    <div className="flex gap-2">
                      {model.installed ? (
                        <>
                          <button
                            onClick={() => isHosting ? onUnhost(model.id) : onHost(model.id)}
                            disabled={isDownloading}
                            className={`px-3 py-1 text-xs font-medium rounded transition-all ${
                              isHosting 
                                ? 'bg-yellow-600 hover:bg-yellow-700 text-white' 
                                : 'bg-green-600 hover:bg-green-700 text-white'
                            } ${isDownloading ? 'opacity-50 cursor-not-allowed' : ''}`}
                          >
                            {isHosting ? 'Stop Earning' : 'Start Earning'}
                          </button>
                          <button
                            onClick={() => handleUninstall(model.id)}
                            disabled={isDownloading}
                            className="px-3 py-1 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Uninstall
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => handleDownload(model.id)}
                          disabled={!isCompatible || isDownloading}
                          className={`px-3 py-1 text-xs font-medium rounded transition-all ${
                            isCompatible && !isDownloading
                              ? 'bg-aipg-orange hover:bg-orange-600 text-white'
                              : 'bg-gray-600 text-gray-400 cursor-not-allowed'
                          }`}
                        >
                          {isDownloading ? 'Downloading...' : 'Start Earning'}
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Download Progress Bar */}
                {isDownloading && (
                  <div className="mt-2">
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div 
                        className="bg-aipg-orange h-2 rounded-full transition-all duration-300" 
                        style={{ width: `${downloadProgress[model.id]?.progress || 0}%` }}
                      ></div>
                    </div>
                    {downloadProgress[model.id] && (
                      <div className="mt-1 text-xs text-gray-400">
                        <div className="flex justify-between">
                          <span>{downloadProgress[model.id].progress.toFixed(1)}% complete</span>
                          {downloadProgress[model.id].speed && (
                            <span>{downloadProgress[model.id].speed}/s</span>
                          )}
                        </div>
                        {downloadProgress[model.id].eta && (
                          <div className="text-gray-500">{downloadProgress[model.id].eta}</div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>

        {filteredModels.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <p className="text-xl mb-2">No models found</p>
            <p>Try changing the filter</p>
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={confirmModal.isOpen}
        onConfirm={confirmUninstall}
        onCancel={() => setConfirmModal({ isOpen: false, modelName: '' })}
        modelName={confirmModal.modelName}
      />
    </motion.div>
  );
}

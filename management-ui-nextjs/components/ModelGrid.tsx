'use client';

import { motion } from 'framer-motion';
import { useMemo } from 'react';
import ModelCard from './ModelCard';

interface ModelGridProps {
  catalog: any;
  selectedModels: Set<string>;
  diskSpace: any;
  filter: 'all' | 'compatible' | 'selected';
  styleFilter: 'all' | 'text-to-image' | 'text-to-video' | 'image-to-video' | 'image-to-image' | 'anime' | 'realistic' | 'generalist' | 'artistic' | 'video';
  gpuInfo: any;
  onToggleModel: (modelName: string) => void;
  onFilterChange: (filter: 'all' | 'compatible' | 'selected') => void;
  onStyleFilterChange: (styleFilter: 'all' | 'text-to-image' | 'text-to-video' | 'image-to-video' | 'image-to-image' | 'anime' | 'realistic' | 'generalist' | 'artistic' | 'video') => void;
  onUninstall: (modelId: string) => void;
  onHost: (modelId: string) => void;
  onUnhost: (modelId: string) => void;
  onDownload: (modelId: string) => void;
  onDownloadAndHost: (modelId: string) => void;
  onSave: () => void;
  onClear: () => void;
}

export default function ModelGrid({
  catalog,
  selectedModels,
  diskSpace,
  filter,
  styleFilter,
  gpuInfo,
  onToggleModel,
  onFilterChange,
  onStyleFilterChange,
  onUninstall,
  onHost,
  onUnhost,
  onDownload,
  onDownloadAndHost,
  onSave,
  onClear,
}: ModelGridProps) {
  const models = catalog?.models || [];
  
  const filteredModels = useMemo(() => {
    return models.filter((model: any) => {
      // Apply capability filter
      if (filter === 'selected') return selectedModels.has(model.id);
      if (filter === 'compatible') {
        const maxVram = gpuInfo?.gpus?.[0]?.vram_available_gb || gpuInfo?.total_memory_gb || 0;
        return model.vram_required_gb <= maxVram;
      }
      
      // Apply style filter
      if (styleFilter !== 'all') {
        if (styleFilter === 'text-to-image' && !model.capability_type?.includes('Text-to-Image')) return false;
        if (styleFilter === 'text-to-video' && !model.capability_type?.includes('Text-to-Video')) return false;
        if (styleFilter === 'image-to-video' && !model.capability_type?.includes('Image-to-Video')) return false;
        if (styleFilter === 'image-to-image' && !model.capability_type?.includes('Image-to-Image')) return false;
        if (styleFilter === 'anime' && model.style !== 'anime') return false;
        if (styleFilter === 'realistic' && model.style !== 'realistic') return false;
        if (styleFilter === 'generalist' && model.style !== 'generalist') return false;
        if (styleFilter === 'artistic' && model.style !== 'artistic') return false;
        if (styleFilter === 'video' && model.style !== 'video') return false;
      }
      
      return true;
    });
  }, [models, filter, styleFilter, selectedModels, gpuInfo]);

  const { totalSize, maxVram } = useMemo(() => {
    const selected = Array.from(selectedModels);
    const selectedModelsList = models.filter((m: any) => selected.includes(m.id));
    return {
      totalSize: selectedModelsList.reduce((sum: number, m: any) => sum + (m.size_gb || 0), 0),
      maxVram: Math.max(...selectedModelsList.map((m: any) => m.vram_required_gb || 0), 0),
    };
  }, [selectedModels, models]);
  

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

      {/* Summary & Volume Selector */}
      {selectedModels.size > 0 && (
        <>
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mb-4 p-4 rounded-lg bg-gradient-to-r from-aipg-orange/20 to-aipg-gold/20 border border-aipg-orange/30"
          >
            <div className="flex justify-between items-center flex-wrap gap-4">
              <div className="flex gap-8">
                <div>
                  <div className="text-3xl font-bold text-aipg-orange">{selectedModels.size}</div>
                  <div className="text-sm text-gray-400">Selected</div>
                </div>
                <div>
                  <div className="text-3xl font-bold text-aipg-gold">{totalSize.toFixed(1)} GB</div>
                  <div className="text-sm text-gray-400">Total Size</div>
                </div>
                <div>
                  <div className="text-3xl font-bold text-orange-400">{maxVram} GB</div>
                  <div className="text-sm text-gray-400">VRAM Required</div>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}

          {/* Simple Filter Tabs */}
          <div className="flex gap-2 mb-6 flex-wrap">
            {[
              { key: 'compatible', label: 'Supported', icon: '✅' },
              { key: 'all', label: 'All Models', icon: '🎯' },
              { key: 'selected', label: 'Selected', icon: '📋' },
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

          {/* Style Filters */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-400 mb-3">Filter by Style:</h3>
            <div className="flex gap-2 flex-wrap">
              {[
                { key: 'all', label: 'All Styles', icon: '🌈' },
                { key: 'anime', label: 'Anime', icon: '🎌' },
                { key: 'realistic', label: 'Realistic', icon: '📸' },
                { key: 'generalist', label: 'General', icon: '🎯' },
                { key: 'artistic', label: 'Artistic', icon: '🎨' },
                { key: 'video', label: 'Video', icon: '🎬' },
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

      {/* Model Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-6">
        {filteredModels.map((model: any, index: number) => {
          const maxVram = gpuInfo?.gpus?.[0]?.vram_available_gb || gpuInfo?.total_memory_gb || 0;
          const isCompatible = model.vram_required_gb <= maxVram;
          const isHosting = model.hosting || false; // This will be set by the API
          
          return (
            <ModelCard
              key={model.id}
              modelName={model.id}
              model={model}
              isSelected={selectedModels.has(model.id)}
              isCompatible={isCompatible}
              isHosting={isHosting}
              onToggle={() => onToggleModel(model.id)}
              onUninstall={model.installed ? () => onUninstall(model.id) : undefined}
              onHost={() => onHost(model.id)}
              onUnhost={() => onUnhost(model.id)}
              onDownload={() => onDownload(model.id)}
              onDownloadAndHost={() => onDownloadAndHost(model.id)}
              index={index}
            />
          );
        })}
      </div>

      {filteredModels.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          <p className="text-xl mb-2">No models found</p>
          <p>Try changing the filter</p>
        </div>
      )}

          {/* Actions */}
          {selectedModels.size > 0 && (
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-white">Ready to Download</h3>
                  <p className="text-sm text-gray-400">
                    {selectedModels.size} model{selectedModels.size !== 1 ? 's' : ''} selected • {totalSize.toFixed(1)} GB • {maxVram} GB memory required
                  </p>
                </div>
                <button
                  onClick={onClear}
                  className="text-sm text-gray-400 hover:text-white transition-colors"
                >
                  Clear All
                </button>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={onClear}
                  className="px-6 py-3 rounded-lg font-medium border border-gray-600 text-gray-300 hover:text-white hover:border-gray-500 transition-all"
                >
                  Cancel
                </button>
                <button
                  onClick={onSave}
                  className="flex-1 px-6 py-3 rounded-lg font-bold aipg-button text-white transition-all transform hover:scale-[1.02] flex items-center justify-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  Download & Start Earning
                </button>
              </div>
            </div>
          )}
    </motion.div>
  );
}


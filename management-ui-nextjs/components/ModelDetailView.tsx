'use client';

import { motion } from 'framer-motion';
import { useState, useEffect } from 'react';
import DownloadProgressPanel from './DownloadProgressPanel';

interface ModelDetailViewProps {
  catalog: any;
  diskSpace: any;
  filter: 'all' | 'compatible' | 'installed';
  styleFilter: 'all' | 'text-to-image' | 'text-to-video' | 'image-to-video' | 'image-to-image' | 'anime' | 'realistic' | 'generalist' | 'artistic' | 'video';
  gpuInfo: any;
  downloadStatus: any;
  onFilterChange: (filter: 'all' | 'compatible' | 'installed') => void;
  onStyleFilterChange: (styleFilter: 'all' | 'text-to-image' | 'text-to-video' | 'image-to-video' | 'image-to-image' | 'anime' | 'realistic' | 'generalist' | 'artistic' | 'video') => void;
  onUninstall: (modelId: string) => void;
  onHost: (modelId: string) => void;
  onUnhost: (modelId: string) => void;
  onDownload: (modelId: string) => void;
  onDownloadAndHost: (modelId: string) => void;
  onCancelDownload: () => void;
  onCatalogRefresh: () => void;
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
        <h3 className="text-xl font-bold text-white mb-4">
          {modelName.includes(',') ? 'Confirm Bulk Uninstall' : 'Confirm Uninstall'}
        </h3>
        <p className="text-gray-300 mb-6">
          {modelName.includes(',') ? (
            <>
              Are you sure you want to uninstall the following models? This will delete all associated files and cannot be undone.
              <div className="mt-3 p-3 bg-gray-800 rounded-lg">
                <div className="text-sm text-gray-400 max-h-32 overflow-y-auto">
                  {modelName.split(', ').map((name, index) => (
                    <div key={index} className="font-semibold text-aipg-orange">• {name}</div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <>
              Are you sure you want to uninstall <span className="font-semibold text-aipg-orange">{modelName}</span>? 
              This will delete all associated files and cannot be undone.
            </>
          )}
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
  downloadStatus,
  onFilterChange,
  onStyleFilterChange,
  onUninstall,
  onHost,
  onUnhost,
  onDownload,
  onDownloadAndHost,
  onCancelDownload,
  onCatalogRefresh,
}: ModelDetailViewProps) {
  const [confirmModal, setConfirmModal] = useState<{ isOpen: boolean; modelName: string }>({ isOpen: false, modelName: '' });
  const [downloadingModels, setDownloadingModels] = useState<Set<string>>(new Set());
  const [downloadProgress, setDownloadProgress] = useState<{ [key: string]: { progress: number; message: string; speed?: string; eta?: string; current_file?: string; files?: any[] } }>({});
  const [hostingModels, setHostingModels] = useState<Set<string>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(25);
  const [localCatalog, setLocalCatalog] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [nsfwFilter, setNsfwFilter] = useState<'all' | 'nsfw-only' | 'sfw-only'>('all');
  const [sortField, setSortField] = useState<string>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());

  // Poll for download state updates (includes files array) every 2 seconds
  useEffect(() => {
    const hasActiveDownloads = downloadingModels.size > 0;
    if (!hasActiveDownloads) return;
    
    let isMounted = true;
    
    const pollInterval = setInterval(async () => {
      if (!isMounted) return;
      
      try {
        const response = await fetch('/api/models/download/status');
        if (!response.ok || !isMounted) return;
        
        const data = await response.json();
        if (data.models && isMounted) {
          // Update download progress with full state including files
          setDownloadProgress(prev => {
            const newProgress = { ...prev };
            for (const [modelId, state] of Object.entries(data.models)) {
              const modelState = state as any;
              if (modelState.is_downloading || modelState.files?.length > 0) {
                newProgress[modelId] = {
                  progress: modelState.progress || 0,
                  message: modelState.message || '',
                  speed: modelState.speed || '',
                  eta: modelState.eta || '',
                  files: modelState.files || [],
                  current_file: modelState.current_file
                };
                
                // Check if download is complete (100% and no longer downloading)
                if (!modelState.is_downloading && modelState.progress >= 100) {
                  console.log(`Download complete for ${modelId}, cleaning up...`);
                  // Remove from downloading set and progress after a delay
                  setTimeout(() => {
                    setDownloadingModels(prevSet => {
                      const newSet = new Set(prevSet);
                      newSet.delete(modelId);
                      return newSet;
                    });
                    setDownloadProgress(prevProg => {
                      const newProg = { ...prevProg };
                      delete newProg[modelId];
                      return newProg;
                    });
                  }, 3000); // 3 second delay to show success
                }
              }
            }
            return newProgress;
          });
        }
      } catch (error) {
        if (isMounted) {
          console.error('Error polling download state:', error);
        }
      }
    }, 2000);
    
    return () => {
      isMounted = false;
      clearInterval(pollInterval);
    };
  }, [downloadingModels.size > 0]); // Only re-run when going from 0 to >0 or vice versa

  // Fetch catalog data with pagination and search
  useEffect(() => {
    const fetchCatalog = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({
          page: currentPage.toString(),
          limit: itemsPerPage.toString(),
          ...(searchTerm && { search: searchTerm }),
          ...(styleFilter !== 'all' && { styleFilter }),
          ...(nsfwFilter !== 'all' && { nsfwFilter }),
          sortField,
          sortDirection
        });
        
        const response = await fetch(`/api/models-catalog?${params}`);
        const data = await response.json();
        setLocalCatalog(data);
      } catch (error) {
        console.error('Failed to fetch catalog:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCatalog();
  }, [currentPage, itemsPerPage, searchTerm, styleFilter, nsfwFilter, sortField, sortDirection]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, styleFilter, nsfwFilter]);

  // Sync global download status with local state (for backwards compatibility)
  useEffect(() => {
    if (downloadStatus?.models && typeof downloadStatus.models === 'object') {
      // New format - per-model status
      Object.entries(downloadStatus.models).forEach(([modelId, state]: [string, any]) => {
        if (state.is_downloading) {
          setDownloadingModels(prev => new Set(prev).add(modelId));
          setDownloadProgress(prev => ({
            ...prev,
            [modelId]: {
              progress: state.progress || 0,
              message: state.message || `Downloading ${modelId}...`,
              speed: state.speed,
              eta: state.eta,
            }
          }));
        }
      });
    } else if (downloadStatus?.is_downloading && downloadStatus?.current_model) {
      // Legacy format - single model
      const modelId = downloadStatus.current_model;
      setDownloadingModels(prev => new Set(prev).add(modelId));
      setDownloadProgress(prev => ({
        ...prev,
        [modelId]: {
          progress: downloadStatus.progress || 0,
          message: `Downloading ${modelId}...`,
          speed: downloadStatus.speed,
          eta: downloadStatus.eta
        }
      }));
    } else if (!downloadStatus?.is_downloading) {
      // Only clear if no models are downloading
      const hasActiveDownloads = downloadStatus?.models && 
        Object.values(downloadStatus.models).some((state: any) => state.is_downloading);
      
      if (!hasActiveDownloads) {
        setDownloadingModels(new Set());
        setDownloadProgress({});
      }
    }
  }, [downloadStatus]);

  // Initialize hosting models from catalog data
  useEffect(() => {
    if (localCatalog?.models) {
      const hosted = new Set<string>();
      localCatalog.models.forEach((model: any) => {
        if (model.hosting) {
          hosted.add(model.id);
        }
      });
      setHostingModels(hosted);
    }
  }, [localCatalog]);

  const models = localCatalog?.models || catalog?.models || [];
  const pagination = localCatalog?.pagination || null;
  
  // Apply client-side filters (compatibility and installed status)
  const filteredModels = models.filter((model: any) => {
    // Apply capability filter
    if (filter === 'compatible') {
      const maxVram = gpuInfo?.gpus?.[0]?.vram_available_gb || gpuInfo?.total_memory_gb || 0;
      return model.vram_required_gb <= maxVram;
    }
    
    // Apply installed filter
    if (filter === 'installed') {
      return model.installed === true;
    }
    
    return true;
  });

  const handleUninstall = (modelId: string) => {
    setConfirmModal({ isOpen: true, modelName: modelId });
  };

  const confirmUninstall = () => {
    if (confirmModal.modelName.includes(',')) {
      // Bulk uninstall
      const modelIds = confirmModal.modelName.split(', ');
      modelIds.forEach(modelId => onUninstall(modelId.trim()));
      setSelectedModels(new Set());
    } else {
      // Single uninstall
      onUninstall(confirmModal.modelName);
    }
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
              
              // Use model from SSE event, fallback to requested modelId
              const targetModel = data.model || modelId;
              
              // Add to downloading set if not already there
              if (targetModel !== modelId) {
                setDownloadingModels(prev => new Set(prev).add(targetModel));
              }
              
              if (data.type === 'progress') {
                setDownloadProgress(prev => ({
                  ...prev,
                  [targetModel]: {
                    progress: data.progress || 0,
                    message: data.message,
                    speed: data.speed,
                    eta: data.eta
                  }
                }));
              } else if (data.type === 'start') {
                setDownloadProgress(prev => ({
                  ...prev,
                  [targetModel]: {
                    progress: 0,
                    message: data.message || 'Starting download...',
                  }
                }));
              } else if (data.type === 'success' || data.type === 'info') {
                setDownloadProgress(prev => ({
                  ...prev,
                  [targetModel]: {
                    progress: prev[targetModel]?.progress || 0,
                    message: data.message,
                  }
                }));
              } else if (data.type === 'complete') {
                setDownloadProgress(prev => ({
                  ...prev,
                  [targetModel]: {
                    progress: 100,
                    message: 'Download complete!',
                  }
                }));
                
                // Remove from downloading set after a delay
                setTimeout(() => {
                  setDownloadingModels(prev => {
                    const newSet = new Set(prev);
                    newSet.delete(targetModel);
                    return newSet;
                  });
                  setDownloadProgress(prev => {
                    const newProgress = { ...prev };
                    delete newProgress[targetModel];
                    return newProgress;
                  });
                }, 2000);
                
                // Refresh catalog to show installed model
                if (data.success) {
                  await onDownloadAndHost(targetModel);
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
      
      // Remove from downloading set after showing error
      setTimeout(() => {
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
      }, 3000);
    }
  };

  const handleCancelFile = async (modelId: string, fileName: string) => {
    try {
      console.log(`Cancelling file: ${fileName} for model: ${modelId}`);
      
      const response = await fetch('/api/models/download/cancel-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId, file_name: fileName })
      });

      const result = await response.json();
      console.log('Cancel file result:', result);

      if (response.ok && result.success) {
        // Update the download state
        setDownloadProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[modelId];
          return newProgress;
        });
        setDownloadingModels(prev => {
          const newSet = new Set(prev);
          newSet.delete(modelId);
          return newSet;
        });
        
        // Show success message
        alert(`Download cancelled for ${modelId}`);
        onCatalogRefresh();
      } else {
        alert(`Failed to cancel: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error cancelling file:', error);
      alert(`Error cancelling download: ${error}`);
    }
  };

  const handleCancelAllFiles = async (modelId: string) => {
    try {
      console.log(`Cancelling all files for model: ${modelId}`);
      
      const response = await fetch('/api/models/download/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId })
      });

      const result = await response.json();
      console.log('Cancel all result:', result);

      if (response.ok && result.success) {
        // Update local state
        setDownloadProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[modelId];
          return newProgress;
        });
        setDownloadingModels(prev => {
          const newSet = new Set(prev);
          newSet.delete(modelId);
          return newSet;
        });
        
        // Show success message
        alert(`Download cancelled for ${modelId}`);
        
        // Refresh catalog to update UI
        onCatalogRefresh();
      } else {
        alert(`Failed to cancel: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error cancelling all files:', error);
      alert(`Error cancelling download: ${error}`);
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
          { key: 'installed', label: 'Installed', icon: '📦' },
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

      {/* NSFW Filter */}
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-400 mb-3">Filter by Content:</h3>
        <div className="flex gap-2 flex-wrap">
          {[
            { key: 'all', label: 'All Content', icon: '🌐' },
            { key: 'sfw-only', label: 'SFW Only', icon: '✅' },
            { key: 'nsfw-only', label: 'NSFW Only', icon: '🔞' },
          ].map(({ key, label, icon }) => (
            <button
              key={key}
              onClick={() => setNsfwFilter(key as any)}
              className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-all ${
                nsfwFilter === key
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

      {/* Active Downloads Panel - Enhanced with Per-File Tracking */}
      {Object.keys(downloadProgress).length > 0 && (
        <div className="mb-6 space-y-4">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <svg className="w-6 h-6 text-aipg-orange animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Active Downloads ({Object.keys(downloadProgress).length})
          </h2>
          
          {Object.entries(downloadProgress).map(([modelId, progress]) => {
            // Convert old progress format to new ModelDownloadState format
            const downloadState = {
              is_downloading: true,
              progress: progress.progress || 0,
              speed: progress.speed || '',
              eta: progress.eta || '',
              current_file: progress.current_file,
              message: progress.message,
              files: progress.files || [],  // Use files if available, otherwise empty
              total_files: progress.files?.length || 0,
              completed_files: progress.files?.filter((f: any) => f.status === 'completed').length || 0
            };
            
            const modelName = modelId.replace(/-/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
            
            return (
              <DownloadProgressPanel
                key={modelId}
                modelId={modelId}
                modelName={modelName}
                downloadState={downloadState}
                onCancelFile={handleCancelFile}
                onCancelAll={handleCancelAllFiles}
              />
            );
          })}
        </div>
      )}

      {/* Search and Pagination Controls */}
      <div className="mb-6 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        {/* Search */}
        <div className="flex-1 max-w-md">
          <div className="relative">
            <input
              type="text"
              placeholder="Search by model name..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-4 py-2 pl-10 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-aipg-orange focus:ring-1 focus:ring-aipg-orange"
            />
            <svg className="absolute left-3 top-2.5 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>

        {/* Items per page */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-400">Show:</span>
          <select
            value={itemsPerPage}
            onChange={(e) => {
              setItemsPerPage(parseInt(e.target.value));
              setCurrentPage(1);
            }}
            className="px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-aipg-orange"
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
          <span className="text-sm text-gray-400">per page</span>
        </div>
      </div>

      {/* Bulk Actions */}
      {selectedModels.size > 0 && (
        <div className="mb-4 p-4 bg-gray-800 rounded-lg border border-gray-600">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-300">
              {selectedModels.size} model{selectedModels.size !== 1 ? 's' : ''} selected
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  // Bulk host action
                  selectedModels.forEach(modelId => {
                    if (!downloadingModels.has(modelId)) {
                      onHost(modelId);
                    }
                  });
                  setSelectedModels(new Set());
                }}
                className="px-3 py-1 text-xs font-medium bg-green-600 hover:bg-green-700 text-white rounded transition-all"
              >
                Start Earning All
              </button>
              <button
                onClick={() => {
                  // Bulk uninstall action
                  setConfirmModal({ 
                    isOpen: true, 
                    modelName: Array.from(selectedModels).join(', ') 
                  });
                }}
                className="px-3 py-1 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded transition-all"
              >
                Uninstall All
              </button>
              <button
                onClick={() => setSelectedModels(new Set())}
                className="px-3 py-1 text-xs font-medium bg-gray-600 hover:bg-gray-700 text-white rounded transition-all"
              >
                Clear Selection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Loading indicator */}
      {loading && (
        <div className="flex items-center justify-center py-8">
          <div className="w-8 h-8 border-4 border-aipg-orange border-t-transparent rounded-full animate-spin"></div>
          <span className="ml-3 text-gray-400">Loading models...</span>
        </div>
      )}

        {/* Windows Explorer Style Table */}
        <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
          {/* Table Header */}
          <div className="bg-gray-800 px-4 py-3 border-b border-gray-700">
            <div className="grid grid-cols-12 gap-1 text-sm font-semibold text-gray-300">
              <div className="col-span-1 flex items-center justify-center">
                <input
                  type="checkbox"
                  checked={selectedModels.size === filteredModels.length && filteredModels.length > 0}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedModels(new Set(filteredModels.map((m: any) => m.id)));
                    } else {
                      setSelectedModels(new Set());
                    }
                  }}
                  className="w-4 h-4 text-aipg-orange bg-gray-700 border-gray-600 rounded focus:ring-aipg-orange focus:ring-2"
                />
              </div>
              <div className="col-span-3 cursor-pointer" onClick={() => {
                if (sortField === 'name') {
                  setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                } else {
                  setSortField('name');
                  setSortDirection('asc');
                }
              }}>
                Name {sortField === 'name' && (sortDirection === 'asc' ? '↑' : '↓')}
              </div>
              <div className="col-span-2 cursor-pointer" onClick={() => {
                if (sortField === 'style') {
                  setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                } else {
                  setSortField('style');
                  setSortDirection('asc');
                }
              }}>
                Style {sortField === 'style' && (sortDirection === 'asc' ? '↑' : '↓')}
              </div>
              <div className="col-span-1 cursor-pointer" onClick={() => {
                if (sortField === 'size_gb') {
                  setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                } else {
                  setSortField('size_gb');
                  setSortDirection('asc');
                }
              }}>
                Size {sortField === 'size_gb' && (sortDirection === 'asc' ? '↑' : '↓')}
              </div>
              <div className="col-span-1 cursor-pointer" onClick={() => {
                if (sortField === 'vram_required_gb') {
                  setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                } else {
                  setSortField('vram_required_gb');
                  setSortDirection('asc');
                }
              }}>
                VRAM Requirement {sortField === 'vram_required_gb' && (sortDirection === 'asc' ? '↑' : '↓')}
              </div>
              <div className="col-span-2">Status</div>
              <div className="col-span-2">Actions</div>
            </div>
          </div>

        {/* Table Body */}
        <div className="divide-y divide-gray-700">
          {filteredModels.map((model: any, index: number) => {
            const maxVram = gpuInfo?.gpus?.[0]?.vram_available_gb || gpuInfo?.total_memory_gb || 0;
            const isCompatible = model.vram_required_gb <= maxVram;
            const isHosting = hostingModels.has(model.id) || model.hosting || false;
            const isDownloading = downloadingModels.has(model.id) || (downloadStatus?.is_downloading && downloadStatus?.current_model === model.id);
            const currentDownloadProgress = downloadProgress[model.id]?.progress || downloadStatus?.progress || 0;

            return (
              <motion.div
                key={model.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="px-4 py-3 hover:bg-gray-800/50 transition-colors"
              >
                <div className="grid grid-cols-12 gap-1 items-center text-sm">
                  {/* Checkbox */}
                  <div className="col-span-1 flex items-center justify-center">
                    <input
                      type="checkbox"
                      checked={selectedModels.has(model.id)}
                      onChange={(e) => {
                        const newSelected = new Set(selectedModels);
                        if (e.target.checked) {
                          newSelected.add(model.id);
                        } else {
                          newSelected.delete(model.id);
                        }
                        setSelectedModels(newSelected);
                      }}
                      className="w-4 h-4 text-aipg-orange bg-gray-700 border-gray-600 rounded focus:ring-aipg-orange focus:ring-2"
                    />
                  </div>

                  {/* Name */}
                  <div className="col-span-3">
                    <div className="font-medium text-white">{model.display_name}</div>
                    <div 
                      className="text-xs text-gray-400 line-clamp-1 cursor-help" 
                      title={model.description}
                    >
                      {model.description}
                    </div>
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
                      {isHosting && model.installed && (
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
                            onClick={() => {
                              if (isHosting) {
                                setHostingModels(prev => {
                                  const newSet = new Set(prev);
                                  newSet.delete(model.id);
                                  return newSet;
                                });
                                onUnhost(model.id);
                              } else {
                                setHostingModels(prev => new Set(prev).add(model.id));
                                onHost(model.id);
                              }
                            }}
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
                      ) : isDownloading ? (
                        <button
                          onClick={() => onCancelDownload()}
                          className="px-3 py-1 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded transition-all flex items-center gap-1"
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                          Cancel
                        </button>
                      ) : (
                        <button
                          onClick={() => handleDownload(model.id)}
                          disabled={!isCompatible}
                          className={`px-3 py-1 text-xs font-medium rounded transition-all ${
                            isCompatible
                              ? 'bg-aipg-orange hover:bg-orange-600 text-white'
                              : 'bg-gray-600 text-gray-400 cursor-not-allowed'
                          }`}
                        >
                          Start Earning
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Download Progress Bar */}
                {isDownloading && (
                  <div className="mt-2">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Downloading...</span>
                      <span>{currentDownloadProgress.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div 
                        className="bg-gradient-to-r from-aipg-orange to-aipg-gold h-2 rounded-full transition-all duration-300" 
                        style={{ width: `${currentDownloadProgress}%` }}
                      ></div>
                    </div>
                    {(downloadProgress[model.id]?.speed || downloadStatus?.speed) && (
                      <div className="mt-1 text-xs text-gray-400">
                        <div className="flex justify-between">
                          <span>{currentDownloadProgress.toFixed(1)}% complete</span>
                          <span>{downloadProgress[model.id]?.speed || downloadStatus?.speed} MB/s</span>
                        </div>
                        {(downloadProgress[model.id]?.eta || downloadStatus?.eta) && (
                          <div className="text-gray-500">ETA: {downloadProgress[model.id]?.eta || downloadStatus?.eta}</div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>

        {filteredModels.length === 0 && !loading && (
          <div className="text-center py-12 text-gray-500">
            <p className="text-xl mb-2">No models found</p>
            <p>Try changing the filter or search term</p>
          </div>
        )}
      </div>

      {/* Pagination Controls */}
      {pagination && !loading && (
        <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          {/* Results info */}
          <div className="text-sm text-gray-400">
            Showing {((pagination.page - 1) * pagination.limit) + 1} to {Math.min(pagination.page * pagination.limit, pagination.total_count)} of {pagination.total_count} models
          </div>

          {/* Pagination buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage(1)}
              disabled={!pagination.has_prev}
              className="px-3 py-2 text-sm bg-gray-800 border border-gray-600 rounded-lg text-gray-300 hover:text-white hover:border-aipg-orange disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              First
            </button>
            <button
              onClick={() => setCurrentPage(currentPage - 1)}
              disabled={!pagination.has_prev}
              className="px-3 py-2 text-sm bg-gray-800 border border-gray-600 rounded-lg text-gray-300 hover:text-white hover:border-aipg-orange disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              Previous
            </button>
            
            {/* Page numbers */}
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                const startPage = Math.max(1, pagination.page - 2);
                const pageNum = startPage + i;
                if (pageNum > pagination.total_pages) return null;
                
                return (
                  <button
                    key={pageNum}
                    onClick={() => setCurrentPage(pageNum)}
                    className={`px-3 py-2 text-sm rounded-lg transition-all ${
                      pageNum === pagination.page
                        ? 'bg-aipg-orange text-white'
                        : 'bg-gray-800 border border-gray-600 text-gray-300 hover:text-white hover:border-aipg-orange'
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              })}
            </div>

            <button
              onClick={() => setCurrentPage(currentPage + 1)}
              disabled={!pagination.has_next}
              className="px-3 py-2 text-sm bg-gray-800 border border-gray-600 rounded-lg text-gray-300 hover:text-white hover:border-aipg-orange disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              Next
            </button>
            <button
              onClick={() => setCurrentPage(pagination.total_pages)}
              disabled={!pagination.has_next}
              className="px-3 py-2 text-sm bg-gray-800 border border-gray-600 rounded-lg text-gray-300 hover:text-white hover:border-aipg-orange disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              Last
            </button>
          </div>
        </div>
      )}

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

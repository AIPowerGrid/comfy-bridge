'use client';

import { useState, useMemo } from 'react';
import { useWallet, useModelVault } from '@/lib/web3';
import { ModelType } from '@/lib/web3/types';
import { motion, AnimatePresence } from 'framer-motion';

const MODEL_TYPE_LABELS: Record<number, string> = {
  [ModelType.TEXT_MODEL]: 'Text/LLM',
  [ModelType.IMAGE_MODEL]: 'Image',
  [ModelType.VIDEO_MODEL]: 'Video',
};

const MODEL_TYPE_COLORS: Record<number, string> = {
  [ModelType.TEXT_MODEL]: 'bg-green-500/20 text-green-300 border-green-500/30',
  [ModelType.IMAGE_MODEL]: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  [ModelType.VIDEO_MODEL]: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
};

// Chain ID to name mapping
const CHAIN_NAMES: Record<number, string> = {
  8453: 'Base',
  84532: 'Base Sepolia',
};

interface ModelVaultStatusProps {
  onStartEarning?: (modelName: string) => void;
  onStopEarning?: (modelName: string) => void;
  onUninstall?: (modelName: string) => void;
  onBatchUninstall?: (modelNames: string[]) => void;
  onDownload?: (modelName: string) => void;
  installedModels?: Set<string>;
  hostedModels?: Set<string>;
  downloadingModels?: Set<string>;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function ModelVaultStatus({ 
  onStartEarning, 
  onStopEarning, 
  onUninstall,
  onBatchUninstall,
  onDownload,
  installedModels = new Set(),
  hostedModels = new Set(),
  downloadingModels = new Set(),
  isCollapsed,
  onToggleCollapse,
}: ModelVaultStatusProps) {
  const { isConnected, address, chainId } = useWallet();
  const { isLoading, error, modelsWithDetails = [], refreshModels } = useModelVault();
  const networkName = CHAIN_NAMES[chainId] || 'Unknown Network';
  // Use external collapse control if provided, otherwise use internal state
  const [internalExpanded, setInternalExpanded] = useState(true);
  const isExpanded = isCollapsed !== undefined ? !isCollapsed : internalExpanded;
  const toggleExpanded = onToggleCollapse || (() => setInternalExpanded(!internalExpanded));
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'image' | 'video' | 'text'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'installed' | 'not-installed' | 'hosting'>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(25);
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
  const [sortField, setSortField] = useState<'name' | 'type' | 'size'>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Filter models based on search and filters
  const filteredModels = useMemo(() => {
    let filtered = modelsWithDetails.filter(({ hash, info }) => {
      if (!info) return false;
      
      const modelName = info.displayName || info.fileName || '';
      const searchLower = searchQuery.toLowerCase();
      
      // Search filter
      if (searchQuery && !modelName.toLowerCase().includes(searchLower) && 
          !info.description?.toLowerCase().includes(searchLower) &&
          !info.baseModel?.toLowerCase().includes(searchLower)) {
        return false;
      }
      
      // Type filter
      if (typeFilter !== 'all') {
        const typeMap: Record<string, ModelType> = {
          'image': ModelType.IMAGE_MODEL,
          'video': ModelType.VIDEO_MODEL,
          'text': ModelType.TEXT_MODEL,
        };
        if (info.modelType !== typeMap[typeFilter]) {
          return false;
        }
      }
      
      // Status filter
      const isInstalled = installedModels.has(modelName) || installedModels.has(info.fileName);
      const isHosted = hostedModels.has(modelName) || hostedModels.has(info.fileName);
      
      if (statusFilter === 'installed' && !isInstalled) return false;
      if (statusFilter === 'not-installed' && isInstalled) return false;
      if (statusFilter === 'hosting' && !isHosted) return false;
      
      return true;
    });

    // Sort
    filtered.sort((a, b) => {
      const aInfo = a.info;
      const bInfo = b.info;
      if (!aInfo || !bInfo) return 0;

      let aVal: string | number = '';
      let bVal: string | number = '';

      switch (sortField) {
        case 'name':
          aVal = (aInfo.displayName || aInfo.fileName || '').toLowerCase();
          bVal = (bInfo.displayName || bInfo.fileName || '').toLowerCase();
          break;
        case 'type':
          aVal = MODEL_TYPE_LABELS[aInfo.modelType] || '';
          bVal = MODEL_TYPE_LABELS[bInfo.modelType] || '';
          break;
        case 'size':
          aVal = Number(aInfo.sizeBytes) || 0;
          bVal = Number(bInfo.sizeBytes) || 0;
          break;
      }

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [modelsWithDetails, searchQuery, typeFilter, statusFilter, installedModels, hostedModels, sortField, sortDirection]);

  // Pagination
  const paginatedModels = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return filteredModels.slice(startIndex, startIndex + itemsPerPage);
  }, [filteredModels, currentPage, itemsPerPage]);

  const totalPages = Math.ceil(filteredModels.length / itemsPerPage);

  // Count models by type
  const typeCounts = useMemo(() => {
    const counts = { image: 0, video: 0, text: 0, total: 0 };
    modelsWithDetails.forEach(({ info }) => {
      if (!info) return;
      counts.total++;
      if (info.modelType === ModelType.IMAGE_MODEL) counts.image++;
      else if (info.modelType === ModelType.VIDEO_MODEL) counts.video++;
      else if (info.modelType === ModelType.TEXT_MODEL) counts.text++;
    });
    return counts;
  }, [modelsWithDetails]);

  const handleSort = (field: 'name' | 'type' | 'size') => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  // Not connected - show connect prompt
  if (!isConnected) {
    return (
      <div className="bg-gradient-to-br from-blue-900/30 via-indigo-900/20 to-purple-900/20 border border-blue-500/50 rounded-xl p-8">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-blue-500/20 flex items-center justify-center">
            <svg className="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">Connect Your Wallet</h2>
          <p className="text-gray-400 mb-6 max-w-md mx-auto">
            Connect your blockchain wallet to view and manage AI models registered on the grid.
            All models are stored on-chain for transparency and security.
          </p>
          <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            <span>Base Network</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="bg-gradient-to-br from-blue-900/20 via-indigo-900/15 to-purple-900/20 rounded-xl p-6 border border-blue-500/30"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className={`w-3 h-3 rounded-full ${isLoading ? 'bg-yellow-500 animate-pulse' : error ? 'bg-red-500' : 'bg-green-500'}`} />
            {!isLoading && !error && (
              <div className="absolute inset-0 w-3 h-3 rounded-full bg-green-500 animate-ping opacity-30" />
            )}
          </div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
            Blockchain Model Registry
            <span className="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-300 rounded-full">
              {networkName}
            </span>
          </h2>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            <p className="text-xs text-gray-500">Connected</p>
            <p className="text-xs text-gray-400 font-mono">
              {address?.slice(0, 6)}...{address?.slice(-4)}
            </p>
          </div>
          <div className="text-sm text-gray-400">
            <span className="font-semibold text-blue-400">{filteredModels.length}</span> models available
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              refreshModels();
            }}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600/50 hover:bg-blue-600 text-white text-sm rounded-lg transition-all disabled:opacity-50 flex items-center gap-2"
          >
            <svg className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {isLoading ? 'Syncing...' : 'Refresh'}
          </button>
          <button
            onClick={toggleExpanded}
            className="p-2 hover:bg-white/5 rounded-lg transition-colors"
          >
            <svg
              className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {/* Type Filter Tabs */}
            <div className="flex gap-2 mb-6 flex-wrap">
              <button
                onClick={() => { setTypeFilter('all'); setCurrentPage(1); }}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                  typeFilter === 'all'
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
                    : 'bg-gray-800 text-gray-300 hover:text-white border border-gray-600 hover:border-blue-500/50'
                }`}
              >
                <span>🔗</span>
                All ({typeCounts.total})
              </button>
              <button
                onClick={() => { setTypeFilter('image'); setCurrentPage(1); }}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                  typeFilter === 'image'
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
                    : 'bg-gray-800 text-gray-300 hover:text-white border border-gray-600 hover:border-blue-500/50'
                }`}
              >
                <span>🖼️</span>
                Image ({typeCounts.image})
              </button>
              <button
                onClick={() => { setTypeFilter('video'); setCurrentPage(1); }}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                  typeFilter === 'video'
                    ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/30'
                    : 'bg-gray-800 text-gray-300 hover:text-white border border-gray-600 hover:border-purple-500/50'
                }`}
              >
                <span>🎬</span>
                Video ({typeCounts.video})
              </button>
              {typeCounts.text > 0 && (
                <button
                  onClick={() => { setTypeFilter('text'); setCurrentPage(1); }}
                  className={`flex items-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                    typeFilter === 'text'
                      ? 'bg-green-600 text-white shadow-lg shadow-green-600/30'
                      : 'bg-gray-800 text-gray-300 hover:text-white border border-gray-600 hover:border-green-500/50'
                  }`}
                >
                  <span>📝</span>
                  Text ({typeCounts.text})
                </button>
              )}
            </div>

            {/* Search and Pagination Controls */}
            <div className="mb-6 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
              {/* Search */}
              <div className="flex-1 max-w-md">
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Search by model name..."
                    value={searchQuery}
                    onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                    className="w-full px-4 py-2 pl-10 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  />
                  <svg className="absolute left-3 top-2.5 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="absolute right-3 top-2.5 text-gray-500 hover:text-white"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>

              {/* Status Filter & Items per page */}
              <div className="flex items-center gap-4">
                <select
                  value={statusFilter}
                  onChange={(e) => { setStatusFilter(e.target.value as any); setCurrentPage(1); }}
                  className="px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
                >
                  <option value="all">All Status</option>
                  <option value="installed">Installed</option>
                  <option value="not-installed">Not Installed</option>
                  <option value="hosting">Currently Hosting</option>
                </select>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">Show:</span>
                  <select
                    value={itemsPerPage}
                    onChange={(e) => {
                      setItemsPerPage(parseInt(e.target.value));
                      setCurrentPage(1);
                    }}
                    className="px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
                  >
                    <option value={10}>10</option>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                  <span className="text-sm text-gray-400">per page</span>
                </div>
              </div>
            </div>

            {/* Bulk Actions */}
            {selectedModels.size > 0 && (
              <div className="mb-4 p-4 bg-blue-900/20 rounded-lg border border-blue-500/30">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <span className="text-sm text-gray-300">
                    {selectedModels.size} model{selectedModels.size !== 1 ? 's' : ''} selected
                  </span>
                  <div className="flex gap-2 flex-wrap">
                    <button
                      onClick={() => {
                        selectedModels.forEach(modelName => onStartEarning?.(modelName));
                        setSelectedModels(new Set());
                      }}
                      className="px-3 py-1 text-xs font-medium bg-green-600 hover:bg-green-700 text-white rounded transition-all"
                    >
                      Start Hosting All
                    </button>
                    {/* Show uninstall button if any selected models are installed */}
                    {Array.from(selectedModels).some(modelName => 
                      installedModels.has(modelName) || 
                      modelsWithDetails.some(({ info }) => 
                        info && (info.displayName === modelName || info.fileName === modelName) && 
                        (installedModels.has(info.displayName || '') || installedModels.has(info.fileName))
                      )
                    ) && (
                      <button
                        onClick={() => {
                          // Only uninstall models that are actually installed
                          const installedSelected = Array.from(selectedModels).filter(modelName => 
                            installedModels.has(modelName) ||
                            modelsWithDetails.some(({ info }) => 
                              info && (info.displayName === modelName || info.fileName === modelName) && 
                              (installedModels.has(info.displayName || '') || installedModels.has(info.fileName))
                            )
                          );
                          // Use batch uninstall if available, otherwise fall back to individual
                          if (onBatchUninstall && installedSelected.length > 0) {
                            onBatchUninstall(installedSelected);
                          } else {
                            installedSelected.forEach(modelName => onUninstall?.(modelName));
                          }
                          setSelectedModels(new Set());
                        }}
                        className="px-3 py-1 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded transition-all"
                      >
                        🗑 Uninstall Selected
                      </button>
                    )}
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

            {/* Table */}
            <div className="bg-gray-900/50 rounded-lg border border-blue-500/20 overflow-hidden">
              {/* Table Header */}
              <div className="bg-gray-800/80 px-4 py-3 border-b border-blue-500/20">
                <div className="grid grid-cols-12 gap-1 text-sm font-semibold text-gray-300">
                  <div className="col-span-1 flex items-center justify-center">
                    <input
                      type="checkbox"
                      checked={selectedModels.size === paginatedModels.length && paginatedModels.length > 0}
                      onChange={(e) => {
                        if (e.target.checked) {
                          const allNames = new Set(paginatedModels.map(({ info }) => info?.displayName || info?.fileName || ''));
                          setSelectedModels(allNames);
                        } else {
                          setSelectedModels(new Set());
                        }
                      }}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500 focus:ring-2"
                    />
                  </div>
                  <div 
                    className="col-span-3 cursor-pointer hover:text-blue-400 transition-colors flex items-center gap-1" 
                    onClick={() => handleSort('name')}
                  >
                    Name {sortField === 'name' && (sortDirection === 'asc' ? '↑' : '↓')}
                  </div>
                  <div 
                    className="col-span-2 cursor-pointer hover:text-blue-400 transition-colors flex items-center gap-1"
                    onClick={() => handleSort('type')}
                  >
                    Type {sortField === 'type' && (sortDirection === 'asc' ? '↑' : '↓')}
                  </div>
                  <div 
                    className="col-span-1 cursor-pointer hover:text-blue-400 transition-colors flex items-center gap-1"
                    onClick={() => handleSort('size')}
                  >
                    Size {sortField === 'size' && (sortDirection === 'asc' ? '↑' : '↓')}
                  </div>
                  <div className="col-span-2">Status</div>
                  <div className="col-span-3">Actions</div>
                </div>
              </div>

              {/* Table Body */}
              <div className="divide-y divide-gray-700/50">
                {paginatedModels.map(({ hash, info }, index) => {
                  if (!info) return null;
                  
                  const modelName = info.displayName || info.fileName || hash;
                  const isInstalled = installedModels.has(modelName) || installedModels.has(info.fileName);
                  const isHosted = hostedModels.has(modelName) || hostedModels.has(info.fileName);
                  const isDownloading = downloadingModels.has(modelName) || downloadingModels.has(info.fileName);

                  return (
                    <motion.div
                      key={hash}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.02 }}
                      className={`px-4 py-3 hover:bg-blue-900/10 transition-colors ${
                        isHosted ? 'bg-green-500/5' : isInstalled ? 'bg-blue-500/5' : ''
                      }`}
                    >
                      <div className="grid grid-cols-12 gap-1 items-center text-sm">
                        {/* Checkbox */}
                        <div className="col-span-1 flex items-center justify-center">
                          <input
                            type="checkbox"
                            checked={selectedModels.has(modelName)}
                            onChange={(e) => {
                              const newSelected = new Set(selectedModels);
                              if (e.target.checked) {
                                newSelected.add(modelName);
                              } else {
                                newSelected.delete(modelName);
                              }
                              setSelectedModels(newSelected);
                            }}
                            className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500 focus:ring-2"
                          />
                        </div>

                        {/* Name */}
                        <div className="col-span-3">
                          <div className="font-medium text-white">{info.displayName || info.fileName}</div>
                          <div 
                            className="text-xs text-gray-400 line-clamp-1 cursor-help" 
                            title={info.description || info.baseModel || ''}
                          >
                            {info.description || info.baseModel || info.fileName}
                          </div>
                        </div>

                        {/* Type */}
                        <div className="col-span-2">
                          <span className={`px-2 py-0.5 text-xs rounded border ${MODEL_TYPE_COLORS[info.modelType] || 'bg-gray-500/20 text-gray-300 border-gray-500/30'}`}>
                            {MODEL_TYPE_LABELS[info.modelType] || 'Unknown'}
                          </span>
                          {info.isNSFW && (
                            <span className="ml-1 px-1.5 py-0.5 bg-red-500/20 text-red-300 text-xs rounded border border-red-500/30">
                              NSFW
                            </span>
                          )}
                        </div>

                        {/* Size */}
                        <div className="col-span-1">
                          <div className="text-gray-300">
                            {info.sizeBytes > 0 ? `${(Number(info.sizeBytes) / 1024 / 1024 / 1024).toFixed(1)} GB` : '-'}
                          </div>
                        </div>

                        {/* Status */}
                        <div className="col-span-2">
                          <div className="flex flex-wrap gap-1">
                            {isHosted && (
                              <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded border border-green-500/50 flex items-center gap-1">
                                <div className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                                Hosting
                              </span>
                            )}
                            {isInstalled && !isHosted && (
                              <span className="px-2 py-1 text-xs bg-blue-500/20 text-blue-400 rounded border border-blue-500/50">
                                Installed
                              </span>
                            )}
                            {isDownloading && (
                              <span className="px-2 py-1 text-xs bg-yellow-500/20 text-yellow-400 rounded border border-yellow-500/50 flex items-center gap-1">
                                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                                </svg>
                                Downloading
                              </span>
                            )}
                            {!isInstalled && !isDownloading && (
                              <span className="px-2 py-1 text-xs bg-gray-500/20 text-gray-400 rounded border border-gray-500/50">
                                Not Installed
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="col-span-3">
                          <div className="flex gap-2">
                            {isHosted ? (
                              <button
                                onClick={() => onStopEarning?.(modelName)}
                                className="px-3 py-1 text-xs font-medium bg-red-600/20 hover:bg-red-600/40 text-red-400 rounded transition-all border border-red-600/30"
                              >
                                ⏹ Stop Hosting
                              </button>
                            ) : isInstalled ? (
                              <button
                                onClick={() => onStartEarning?.(modelName)}
                                className="px-3 py-1 text-xs font-medium bg-green-600/20 hover:bg-green-600/40 text-green-400 rounded transition-all border border-green-600/30"
                              >
                                ▶ Start Hosting
                              </button>
                            ) : isDownloading ? (
                              <button
                                disabled
                                className="px-3 py-1 text-xs font-medium bg-yellow-600/20 text-yellow-400 rounded border border-yellow-600/30 cursor-not-allowed flex items-center gap-1"
                              >
                                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                                </svg>
                                Downloading...
                              </button>
                            ) : (
                              <button
                                onClick={() => onDownload?.(modelName)}
                                className="px-3 py-1 text-xs font-medium bg-green-600/20 hover:bg-green-600/40 text-green-400 rounded transition-all border border-green-600/30"
                              >
                                ▶ Start Hosting
                              </button>
                            )}
                            {isInstalled && (
                              <button
                                onClick={() => onUninstall?.(modelName)}
                                className="px-3 py-1 text-xs font-medium bg-gray-700/50 hover:bg-red-600/30 text-gray-400 hover:text-red-400 rounded transition-all border border-gray-600/30 hover:border-red-600/30"
                                title="Uninstall model"
                              >
                                🗑
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>

              {paginatedModels.length === 0 && !isLoading && (
                <div className="text-center py-12 text-gray-500">
                  <p className="text-xl mb-2">No models found</p>
                  <p>Try changing the filter or search term</p>
                  {(searchQuery || typeFilter !== 'all' || statusFilter !== 'all') && (
                    <button
                      onClick={() => {
                        setSearchQuery('');
                        setTypeFilter('all');
                        setStatusFilter('all');
                      }}
                      className="mt-4 text-blue-400 hover:text-blue-300 text-sm"
                    >
                      Clear all filters
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
                {/* Results info */}
                <div className="text-sm text-gray-400">
                  Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, filteredModels.length)} of {filteredModels.length} models
                </div>

                {/* Pagination buttons */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                    className="px-3 py-2 text-sm bg-gray-800 border border-gray-600 rounded-lg text-gray-300 hover:text-white hover:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    First
                  </button>
                  <button
                    onClick={() => setCurrentPage(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="px-3 py-2 text-sm bg-gray-800 border border-gray-600 rounded-lg text-gray-300 hover:text-white hover:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    Previous
                  </button>
                  
                  {/* Page numbers */}
                  <div className="flex items-center gap-1">
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      const startPage = Math.max(1, currentPage - 2);
                      const pageNum = startPage + i;
                      if (pageNum > totalPages) return null;
                      
                      return (
                        <button
                          key={pageNum}
                          onClick={() => setCurrentPage(pageNum)}
                          className={`px-3 py-2 text-sm rounded-lg transition-all ${
                            pageNum === currentPage
                              ? 'bg-blue-600 text-white'
                              : 'bg-gray-800 border border-gray-600 text-gray-300 hover:text-white hover:border-blue-500'
                          }`}
                        >
                          {pageNum}
                        </button>
                      );
                    })}
                  </div>

                  <button
                    onClick={() => setCurrentPage(currentPage + 1)}
                    disabled={currentPage === totalPages}
                    className="px-3 py-2 text-sm bg-gray-800 border border-gray-600 rounded-lg text-gray-300 hover:text-white hover:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    Next
                  </button>
                  <button
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage === totalPages}
                    className="px-3 py-2 text-sm bg-gray-800 border border-gray-600 rounded-lg text-gray-300 hover:text-white hover:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    Last
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

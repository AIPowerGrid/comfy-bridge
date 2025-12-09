'use client';

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface GPUInfoProps {
  gpuInfo: {
    available: boolean;
    gpus: Array<{
      name: string;
      memory_gb: number;
      vram_used_gb?: number;
      vram_available_gb?: number;
      vram_percent_used?: number;
    }>;
    total_memory_gb: number;
    total_vram_used_gb?: number;
  } | null;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export default function GPUInfo({ gpuInfo, isCollapsed = false, onToggleCollapse }: GPUInfoProps) {
  const [sortField, setSortField] = useState<'name' | 'size'>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const sortedGpus = useMemo(() => {
    if (!gpuInfo?.gpus) return [];
    
    return [...gpuInfo.gpus].sort((a, b) => {
      let aVal: string | number;
      let bVal: string | number;

      switch (sortField) {
        case 'name':
          aVal = a.name.toLowerCase();
          bVal = b.name.toLowerCase();
          break;
        case 'size':
          aVal = a.memory_gb;
          bVal = b.memory_gb;
          break;
        default:
          return 0;
      }

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }, [gpuInfo?.gpus, sortField, sortDirection]);

  const handleSort = (field: 'name' | 'size') => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  if (!gpuInfo) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-effect rounded-xl border border-aipg-orange/20"
    >
      {/* Collapsible Header */}
      <div 
        className="flex items-center justify-between p-6 cursor-pointer hover:bg-gray-800/30 transition-colors"
        onClick={onToggleCollapse}
      >
        <div className="flex items-center gap-3">
          <svg className="w-6 h-6 text-aipg-orange" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
          </svg>
          <div>
            <h2 className="text-2xl font-bold text-white">GPU Information</h2>
            <p className="text-sm text-gray-400">
              {gpuInfo.available ? `${gpuInfo.gpus.length} GPU${gpuInfo.gpus.length !== 1 ? 's' : ''} detected` : 'No GPU detected'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {gpuInfo.available && (
            <span className="px-3 py-1 text-xs bg-green-500/20 text-green-400 rounded-full border border-green-500/50">
              {gpuInfo.total_memory_gb} GB Total VRAM
            </span>
          )}
          <svg 
            className={`w-5 h-5 text-gray-400 transition-transform ${isCollapsed ? 'rotate-180' : ''}`}
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Collapsible Content */}
      <AnimatePresence>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-6 pb-6">
              {!gpuInfo.available ? (
                <div className="text-center py-8">
                  <div className="text-yellow-500 text-6xl mb-4">⚠️</div>
                  <p className="text-xl text-gray-300 mb-2">No GPU Detected</p>
                  <p className="text-gray-500">Running in CPU mode. Some models may not be available.</p>
                </div>
              ) : (
                <>
                  {/* Table */}
                  <div className="bg-gray-900/50 rounded-lg border border-aipg-orange/20 overflow-hidden">
                    {/* Table Header */}
                    <div className="bg-gray-800/80 px-4 py-3 border-b border-aipg-orange/20">
                      <div className="grid grid-cols-12 gap-2 text-sm font-semibold text-gray-300">
                        <div className="col-span-1 flex items-center justify-center">
                          #
                        </div>
                        <div 
                          className="col-span-7 cursor-pointer hover:text-aipg-orange transition-colors flex items-center gap-1" 
                          onClick={(e) => { e.stopPropagation(); handleSort('name'); }}
                        >
                          GPU Name {sortField === 'name' && (sortDirection === 'asc' ? '↑' : '↓')}
                        </div>
                        <div 
                          className="col-span-4 cursor-pointer hover:text-aipg-orange transition-colors flex items-center gap-1"
                          onClick={(e) => { e.stopPropagation(); handleSort('size'); }}
                        >
                          VRAM {sortField === 'size' && (sortDirection === 'asc' ? '↑' : '↓')}
                        </div>
                      </div>
                    </div>

                    {/* Table Body */}
                    <div className="divide-y divide-gray-700/50">
                      {sortedGpus.map((gpu, index) => (
                        <motion.div
                          key={index}
                          initial={{ opacity: 0, x: -20 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: index * 0.05 }}
                          className="px-4 py-4 hover:bg-aipg-orange/5 transition-colors"
                        >
                          <div className="grid grid-cols-12 gap-2 items-center text-sm">
                            {/* Index */}
                            <div className="col-span-1 flex items-center justify-center">
                              <span className="text-xs font-bold text-aipg-orange bg-aipg-orange/20 px-2 py-1 rounded-full">
                                {index + 1}
                              </span>
                            </div>

                            {/* Name */}
                            <div className="col-span-7">
                              <div className="font-medium text-white text-base">{gpu.name}</div>
                            </div>

                            {/* VRAM Size */}
                            <div className="col-span-4">
                              <div className="text-2xl font-bold text-aipg-gold">
                                {gpu.memory_gb} GB
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>

                  {/* Summary Footer */}
                  {gpuInfo.gpus.length > 1 && (
                    <div className="mt-4 p-3 rounded-lg bg-aipg-orange/10 border border-aipg-orange/30">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-300">
                          <span className="font-semibold text-aipg-orange">{gpuInfo.gpus.length} GPUs</span> configured
                        </span>
                        <span className="text-gray-300">
                          Total VRAM: <span className="font-bold text-aipg-gold">{gpuInfo.total_memory_gb} GB</span>
                        </span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

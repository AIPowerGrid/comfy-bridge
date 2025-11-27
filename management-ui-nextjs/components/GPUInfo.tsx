'use client';

import { motion } from 'framer-motion';

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
      <motion.div
        initial={false}
        animate={{ height: isCollapsed ? 0 : 'auto' }}
        transition={{ duration: 0.3 }}
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
              {gpuInfo.gpus.length > 1 && (
                <div className="mb-4 p-3 rounded-lg bg-aipg-orange/10 border border-aipg-orange/30">
                  <p className="text-sm text-gray-300">
                    <span className="font-semibold text-aipg-orange">{gpuInfo.gpus.length} GPUs detected</span> - Total VRAM: {gpuInfo.total_memory_gb} GB
                  </p>
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {gpuInfo.gpus.map((gpu, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: index * 0.1 }}
                    className="relative overflow-hidden rounded-lg p-6 bg-gradient-to-br from-aipg-orange/20 to-aipg-gold/20 border border-aipg-orange/30"
                  >
                    <div className="relative z-10">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-bold text-aipg-orange bg-aipg-orange/20 px-2 py-1 rounded-full">
                          GPU {index + 1}
                        </span>
                      </div>
                      <h3 className="text-lg font-semibold mb-2 text-white">{gpu.name}</h3>
                      
                      {/* VRAM Usage Bar */}
                      {gpu.vram_used_gb !== undefined && gpu.vram_used_gb > 0 && (
                        <div className="mb-3">
                          <div className="flex justify-between text-xs text-gray-400 mb-1">
                            <span>VRAM Usage</span>
                            <span>{gpu.vram_percent_used}%</span>
                          </div>
                          <div className="relative w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${gpu.vram_percent_used}%` }}
                              transition={{ duration: 1, ease: "easeOut" }}
                              className={`absolute h-full rounded-full ${
                                (gpu.vram_percent_used || 0) > 90 ? 'bg-red-500' :
                                (gpu.vram_percent_used || 0) > 75 ? 'bg-yellow-500' :
                                'bg-gradient-to-r from-aipg-orange to-aipg-gold'
                              }`}
                            />
                          </div>
                          <div className="flex justify-between text-xs text-gray-500 mt-1">
                            <span>{gpu.vram_used_gb} GB used</span>
                            <span>{gpu.vram_available_gb} GB free</span>
                          </div>
                        </div>
                      )}
                      
                      <div className="text-4xl font-bold text-aipg-gold glow-text-gold">
                        {gpu.vram_available_gb !== undefined ? gpu.vram_available_gb : gpu.memory_gb} GB
                      </div>
                      <p className="text-sm text-gray-400 mt-2">
                        {gpu.vram_used_gb !== undefined && gpu.vram_used_gb > 0 
                          ? `Available of ${gpu.memory_gb} GB Total`
                          : 'Total VRAM Available'
                        }
                      </p>
                    </div>
                    <div className="absolute top-0 right-0 w-32 h-32 bg-aipg-orange/10 rounded-full blur-3xl"></div>
                  </motion.div>
                ))}
              </div>
            </>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}


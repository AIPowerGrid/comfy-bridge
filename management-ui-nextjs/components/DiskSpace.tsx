'use client';

import { motion } from 'framer-motion';
import { useState } from 'react';

interface DiskSpaceProps {
  diskSpace: {
    name: string;
    display_name: string;
    mount_point: string;
    total_gb: number;
    used_gb: number;
    free_gb: number;
    percent_used: number;
    models_count: number;
    models: string[];
  } | null;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export default function DiskSpace({ diskSpace, isCollapsed = false, onToggleCollapse }: DiskSpaceProps) {
  const [showModels, setShowModels] = useState(false);
  
  if (!diskSpace) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="glass-effect rounded-xl border border-aipg-gold/20"
    >
      {/* Collapsible Header */}
      <div 
        className="flex items-center justify-between p-6 cursor-pointer hover:bg-gray-800/30 transition-colors"
        onClick={onToggleCollapse}
      >
        <div className="flex items-center gap-3">
          <svg className="w-6 h-6 text-aipg-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" />
          </svg>
          <div>
            <h2 className="text-2xl font-bold text-white">Disk Usage</h2>
            <p className="text-sm text-gray-400">{diskSpace.mount_point}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {diskSpace.models_count > 0 && (
            <span className="px-3 py-1 text-xs bg-aipg-orange/20 text-aipg-orange rounded-full border border-aipg-orange/30">
              {diskSpace.models_count} file{diskSpace.models_count !== 1 ? 's' : ''} installed
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
        <div className="px-6 pb-6 space-y-4">
          {/* Progress Bar */}
          <div className="relative h-4 bg-gray-700 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${diskSpace.percent_used}%` }}
              transition={{ duration: 1, ease: "easeOut" }}
              className={`absolute h-full rounded-full ${
                diskSpace.percent_used > 90 ? 'bg-red-500' :
                diskSpace.percent_used > 75 ? 'bg-yellow-500' :
                'bg-gradient-to-r from-aipg-orange to-aipg-gold'
              }`}
            />
          </div>
          
          {/* Usage Information */}
          <div className="flex justify-between items-center text-sm">
            <div className="text-gray-400">Disk Usage</div>
            <div className="flex items-center gap-4">
              <span className="text-gray-300 font-bold">{diskSpace.used_gb} GB / {diskSpace.total_gb} GB used</span>
              <span className="text-gray-300 font-bold">{diskSpace.percent_used}%</span>
            </div>
          </div>
          
          {/* Model List Toggle */}
          {diskSpace.models_count > 0 && (
            <div className="pt-3 border-t border-white/10">
              <button
                onClick={() => setShowModels(!showModels)}
                className="text-xs font-semibold text-aipg-orange bg-aipg-orange/20 px-3 py-1 rounded-full border border-aipg-orange/30 hover:bg-aipg-orange/30 transition-all"
              >
                {showModels ? 'Hide' : 'Show'} {diskSpace.models_count} installed file{diskSpace.models_count !== 1 ? 's' : ''}
              </button>
              
              {/* Expanded model list */}
              {showModels && diskSpace.models.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-3"
                >
                  <div className="text-xs font-semibold text-gray-400 mb-2">Installed files:</div>
                  <div className="max-h-40 overflow-y-auto space-y-1">
                    {diskSpace.models.map((model, idx) => (
                      <div key={idx} className="text-xs text-gray-300 pl-2 font-mono">
                        • {model}
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}


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
}

export default function DiskSpace({ diskSpace }: DiskSpaceProps) {
  const [showModels, setShowModels] = useState(false);
  
  if (!diskSpace) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="glass-effect rounded-xl p-6 border border-aipg-gold/20"
    >
      <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
        <svg className="w-6 h-6 text-aipg-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" />
        </svg>
        {diskSpace.display_name}
      </h2>
      
      <div className="space-y-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm text-gray-400">{diskSpace.mount_point}</div>
          {diskSpace.models_count > 0 && (
            <button
              onClick={() => setShowModels(!showModels)}
              className="text-xs font-semibold text-aipg-orange bg-aipg-orange/20 px-3 py-1 rounded-full border border-aipg-orange/30 hover:bg-aipg-orange/30 transition-all"
            >
              {diskSpace.models_count} model{diskSpace.models_count !== 1 ? 's' : ''} installed
            </button>
          )}
        </div>
        
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
        
        <div className="flex justify-between text-sm">
          <span className="text-gray-300 font-semibold">{diskSpace.free_gb} GB free</span>
          <span className="text-gray-400">{diskSpace.used_gb} GB / {diskSpace.total_gb} GB used</span>
          <span className="text-gray-500">{diskSpace.percent_used}%</span>
        </div>
        
        {/* Expanded model list */}
        {showModels && diskSpace.models.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-3 pt-3 border-t border-white/10"
          >
            <div className="text-xs font-semibold text-gray-400 mb-2">Installed models:</div>
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
    </motion.div>
  );
}


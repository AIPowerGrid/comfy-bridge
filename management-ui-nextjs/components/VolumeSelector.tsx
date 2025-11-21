'use client';

import { motion } from 'framer-motion';

interface Volume {
  path: string;
  display_name: string;
  free_gb: number;
}

interface VolumeSelectorProps {
  volumes: Volume[];
  selectedVolume: string;
  onSelect: (path: string) => void;
  requiredSpace: number;
}

export default function VolumeSelector({ volumes, selectedVolume, onSelect, requiredSpace }: VolumeSelectorProps) {
  if (volumes.length <= 1) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-effect rounded-xl p-4 border border-aipg-orange/20 mb-4"
    >
      <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
        <svg className="w-4 h-4 text-aipg-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" />
        </svg>
        Download Location (Required: {requiredSpace} GB)
      </h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {volumes.map((volume) => {
          const hasEnoughSpace = volume.free_gb >= requiredSpace;
          const isSelected = selectedVolume === volume.path;
          
          return (
            <button
              key={volume.path}
              onClick={() => hasEnoughSpace && onSelect(volume.path)}
              disabled={!hasEnoughSpace}
              className={`relative p-3 rounded-lg border-2 transition-all text-left ${
                isSelected
                  ? 'border-aipg-orange bg-aipg-orange/20'
                  : hasEnoughSpace
                  ? 'border-white/10 hover:border-aipg-orange/50 bg-aipg-darkGray'
                  : 'border-red-500/30 bg-red-500/10 opacity-50 cursor-not-allowed'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-white text-sm">{volume.display_name}</span>
                {isSelected && (
                  <div className="w-5 h-5 rounded-full bg-aipg-orange flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
              </div>
              <div className="text-xs text-gray-400">{volume.path}</div>
              <div className={`text-xs mt-1 font-semibold ${hasEnoughSpace ? 'text-green-400' : 'text-red-400'}`}>
                {volume.free_gb} GB free {!hasEnoughSpace && '(Insufficient)'}
              </div>
            </button>
          );
        })}
      </div>
    </motion.div>
  );
}

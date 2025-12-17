'use client';

import { motion } from 'framer-motion';
import { useState } from 'react';

interface DriveInfo {
  name: string;
  display_name: string;
  mount_point: string;
  total_gb: number;
  used_gb: number;
  free_gb: number;
  percent_used: number;
  models_count: number;
  models: string[];
}

interface DiskSpaceData {
  drives?: DriveInfo[];
  totals?: {
    total_gb: number;
    used_gb: number;
    free_gb: number;
    models_count: number;
  };
  // Legacy single-drive fields for backwards compatibility
  name?: string;
  display_name?: string;
  mount_point?: string;
  total_gb?: number;
  used_gb?: number;
  free_gb?: number;
  percent_used?: number;
  models_count?: number;
  models?: string[];
}

interface DiskSpaceProps {
  diskSpace: DiskSpaceData | null;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

function DriveCard({ drive, showModelsInitially = false }: { drive: DriveInfo; showModelsInitially?: boolean }) {
  const [showModels, setShowModels] = useState(showModelsInitially);

  return (
    <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
      {/* Drive Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-aipg-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2 1.5 3 3 3h10c1.5 0 3-1 3-3V7c0-2-1.5-3-3-3H7c-1.5 0-3 1-3 3z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h8" />
          </svg>
          <div>
            <span className="font-semibold text-white">{drive.display_name}</span>
            <span className="text-xs text-gray-400 ml-2 font-mono">{drive.mount_point}</span>
          </div>
        </div>
        {drive.models_count > 0 && (
          <span className="px-2 py-0.5 text-xs bg-aipg-orange/20 text-aipg-orange rounded-full border border-aipg-orange/30">
            {drive.models_count} file{drive.models_count !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Progress Bar */}
      <div className="relative h-3 bg-gray-700 rounded-full overflow-hidden mb-2">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${drive.percent_used}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className={`absolute h-full rounded-full ${
            drive.percent_used > 90 ? 'bg-red-500' :
            drive.percent_used > 75 ? 'bg-yellow-500' :
            'bg-gradient-to-r from-aipg-orange to-aipg-gold'
          }`}
        />
      </div>

      {/* Usage Stats */}
      <div className="flex justify-between items-center text-xs text-gray-400">
        <span>{drive.used_gb.toFixed(1)} GB used</span>
        <span>{drive.free_gb.toFixed(1)} GB free</span>
        <span className="font-semibold text-gray-300">{drive.total_gb.toFixed(1)} GB total</span>
      </div>

      {/* Model List Toggle */}
      {drive.models_count > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-700/50">
          <button
            onClick={() => setShowModels(!showModels)}
            className="text-xs font-semibold text-aipg-orange bg-aipg-orange/10 px-2 py-1 rounded border border-aipg-orange/20 hover:bg-aipg-orange/20 transition-all"
          >
            {showModels ? 'Hide' : 'Show'} files
          </button>
          
          {showModels && drive.models.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-2"
            >
              <div className="max-h-32 overflow-y-auto space-y-0.5">
                {drive.models.map((model, idx) => (
                  <div key={idx} className="text-xs text-gray-300 font-mono truncate" title={model}>
                    {model}
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </div>
      )}
    </div>
  );
}

export default function DiskSpace({ diskSpace, isCollapsed = false, onToggleCollapse }: DiskSpaceProps) {
  if (!diskSpace) return null;

  // Handle both new multi-drive format and legacy single-drive format
  const drives = diskSpace.drives || (diskSpace.name ? [{
    name: diskSpace.name,
    display_name: diskSpace.display_name || diskSpace.name,
    mount_point: diskSpace.mount_point || '',
    total_gb: diskSpace.total_gb || 0,
    used_gb: diskSpace.used_gb || 0,
    free_gb: diskSpace.free_gb || 0,
    percent_used: diskSpace.percent_used || 0,
    models_count: diskSpace.models_count || 0,
    models: diskSpace.models || [],
  }] : []);

  const totals = diskSpace.totals || {
    total_gb: drives.reduce((sum, d) => sum + d.total_gb, 0),
    used_gb: drives.reduce((sum, d) => sum + d.used_gb, 0),
    free_gb: drives.reduce((sum, d) => sum + d.free_gb, 0),
    models_count: drives.reduce((sum, d) => sum + d.models_count, 0),
  };

  const totalPercentUsed = totals.total_gb > 0 
    ? Math.round((totals.used_gb / totals.total_gb) * 100 * 10) / 10 
    : 0;

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
            <p className="text-sm text-gray-400">
              {drives.length} drive{drives.length !== 1 ? 's' : ''} • {totals.total_gb.toFixed(1)} GB total
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {totals.models_count > 0 && (
            <span className="px-3 py-1 text-xs bg-aipg-orange/20 text-aipg-orange rounded-full border border-aipg-orange/30">
              {totals.models_count} model file{totals.models_count !== 1 ? 's' : ''} installed
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
          {/* Total Progress Bar (all drives combined) */}
          {drives.length > 1 && (
            <div className="mb-4">
              <div className="text-sm text-gray-400 mb-2">Combined Storage</div>
              <div className="relative h-4 bg-gray-700 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${totalPercentUsed}%` }}
                  transition={{ duration: 1, ease: "easeOut" }}
                  className={`absolute h-full rounded-full ${
                    totalPercentUsed > 90 ? 'bg-red-500' :
                    totalPercentUsed > 75 ? 'bg-yellow-500' :
                    'bg-gradient-to-r from-aipg-orange to-aipg-gold'
                  }`}
                />
              </div>
              <div className="flex justify-between items-center text-sm mt-1">
                <span className="text-gray-400">{totals.used_gb.toFixed(1)} GB used</span>
                <span className="text-gray-300 font-bold">{totalPercentUsed}%</span>
                <span className="text-gray-400">{totals.free_gb.toFixed(1)} GB free</span>
              </div>
            </div>
          )}

          {/* Individual Drive Cards */}
          <div className={`grid gap-3 ${drives.length > 1 ? 'md:grid-cols-2' : ''}`}>
            {drives.map((drive, idx) => (
              <DriveCard key={drive.name || idx} drive={drive} />
            ))}
          </div>

          {drives.length === 0 && (
            <div className="text-center text-gray-400 py-4">
              No drives detected
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}

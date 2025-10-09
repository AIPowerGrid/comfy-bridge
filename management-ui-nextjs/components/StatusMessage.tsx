'use client';

import { motion } from 'framer-motion';

interface StatusMessageProps {
  type: 'success' | 'error' | 'info';
  message: string;
}

export default function StatusMessage({ type, message }: StatusMessageProps) {
  const colors = {
    success: 'from-green-500/20 to-green-600/20 border-green-500/50',
    error: 'from-red-500/20 to-red-600/20 border-red-500/50',
    info: 'from-blue-500/20 to-blue-600/20 border-blue-500/50',
  };

  const icons = {
    success: (
      <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    error: (
      <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    info: (
      <svg className="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className={`glass-effect rounded-xl p-4 mb-6 border bg-gradient-to-r ${colors[type]} flex items-center gap-3`}
    >
      {icons[type]}
      <p className="flex-1 text-white">{message}</p>
    </motion.div>
  );
}


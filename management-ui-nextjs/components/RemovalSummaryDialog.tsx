'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface RemovalItem {
  name: string;
  type: 'model' | 'dependency' | 'file';
  size?: string;
}

interface RemovalSummaryDialogProps {
  isOpen: boolean;
  items: RemovalItem[];
  onConfirm: () => void;
  onCancel: () => void;
  title?: string;
  confirmText?: string;
}

export default function RemovalSummaryDialog({
  isOpen,
  items,
  onConfirm,
  onCancel,
  title = 'Confirm Removal',
  confirmText = 'OK, Restart Containers'
}: RemovalSummaryDialogProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center"
        >
          <motion.div
            initial={{ scale: 0.9, y: 20 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.9, y: 20 }}
            className="glass-effect rounded-2xl p-6 border border-aipg-orange/30 max-w-lg w-full mx-4 max-h-[80vh] overflow-hidden flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
                <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">{title}</h3>
                <p className="text-sm text-gray-400">Review items to be removed</p>
              </div>
            </div>

            {/* Items List */}
            <div className="flex-1 overflow-y-auto mb-6">
              <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
                <p className="text-sm text-gray-300 mb-3">
                  The following items will be removed:
                </p>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {items.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between py-2 px-3 bg-gray-900/50 rounded border border-gray-700"
                    >
                      <div className="flex items-center gap-2">
                        {item.type === 'model' && (
                          <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                          </svg>
                        )}
                        {item.type === 'dependency' && (
                          <svg className="w-4 h-4 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                        )}
                        {item.type === 'file' && (
                          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                          </svg>
                        )}
                        <span className="text-sm text-white font-medium">{item.name}</span>
                        <span className="text-xs text-gray-500 capitalize">({item.type})</span>
                      </div>
                      {item.size && (
                        <span className="text-xs text-gray-400">{item.size}</span>
                      )}
                    </div>
                  ))}
                </div>

                {items.length === 0 && (
                  <p className="text-center text-gray-500 py-4">No items to remove</p>
                )}
              </div>
            </div>

            {/* Summary */}
            {items.length > 0 && (
              <div className="mb-6 p-3 bg-yellow-900/20 border border-yellow-500/30 rounded-lg">
                <div className="flex items-start gap-2">
                  <svg className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <div className="text-sm text-yellow-200">
                    <strong>Warning:</strong> Containers will restart after removal. This will temporarily interrupt any running jobs.
                  </div>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={onCancel}
                className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={onConfirm}
                disabled={items.length === 0}
                className="flex-1 px-4 py-3 bg-gradient-to-r from-aipg-orange to-aipg-gold hover:from-aipg-orange/90 hover:to-aipg-gold/90 text-white rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-aipg-orange/30"
              >
                {confirmText}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}


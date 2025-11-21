'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface RestartCountdownProps {
  isVisible: boolean;
  onComplete: () => void;
  onCancel?: () => void;
  message?: string;
  countdown?: number;
  showCancel?: boolean;
}

export default function RestartCountdown({
  isVisible,
  onComplete,
  onCancel,
  message = 'Containers will restart',
  countdown = 5,
  showCancel = false
}: RestartCountdownProps) {
  const [seconds, setSeconds] = useState(countdown);
  const [isCountingDown, setIsCountingDown] = useState(false);

  useEffect(() => {
    if (isVisible && !isCountingDown) {
      setSeconds(countdown);
      setIsCountingDown(true);
    }
  }, [isVisible, countdown]);

  useEffect(() => {
    if (!isCountingDown || seconds === 0) return;

    const timer = setInterval(() => {
      setSeconds(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          setIsCountingDown(false);
          onComplete();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isCountingDown, seconds, onComplete]);

  const handleCancel = () => {
    setIsCountingDown(false);
    setSeconds(countdown);
    if (onCancel) onCancel();
  };

  return (
    <AnimatePresence>
      {isVisible && (
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
            className="glass-effect rounded-2xl p-8 border border-aipg-orange/30 max-w-md w-full mx-4"
          >
            <div className="text-center">
              {/* Animated Icon */}
              <div className="mb-6 flex justify-center">
                <div className="relative">
                  <svg 
                    className="w-20 h-20 text-aipg-orange animate-spin"
                    fill="none" 
                    viewBox="0 0 24 24"
                  >
                    <circle 
                      className="opacity-25" 
                      cx="12" 
                      cy="12" 
                      r="10" 
                      stroke="currentColor" 
                      strokeWidth="4"
                    />
                    <path 
                      className="opacity-75" 
                      fill="currentColor" 
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-4xl font-bold text-white">{seconds}</span>
                  </div>
                </div>
              </div>

              {/* Message */}
              <h3 className="text-2xl font-bold text-white mb-2">
                {message}
              </h3>
              <p className="text-gray-400 mb-6">
                Restarting in {seconds} second{seconds !== 1 ? 's' : ''}...
              </p>

              {/* Progress Bar */}
              <div className="w-full bg-gray-700 rounded-full h-2 mb-6">
                <motion.div
                  className="bg-gradient-to-r from-aipg-orange to-aipg-gold h-2 rounded-full"
                  initial={{ width: '100%' }}
                  animate={{ width: `${(seconds / countdown) * 100}%` }}
                  transition={{ duration: 1, ease: 'linear' }}
                />
              </div>

              {/* Cancel Button */}
              {showCancel && onCancel && (
                <button
                  onClick={handleCancel}
                  className="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                >
                  Cancel
                </button>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}


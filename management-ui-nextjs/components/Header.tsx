'use client';

import { motion } from 'framer-motion';
import { useState, useEffect } from 'react';

export default function Header() {
  const [isEarning, setIsEarning] = useState(false);
  const [workerStatus, setWorkerStatus] = useState('unknown');

  useEffect(() => {
    // Check worker status periodically
    const checkStatus = async () => {
      try {
        const response = await fetch('/api/grid-config');
        const config = await response.json();
        if (config.gridApiKey && config.workerName) {
          // TODO: Check actual worker status from grid API
          setWorkerStatus('configured');
        } else {
          setWorkerStatus('not_configured');
        }
      } catch (error) {
        setWorkerStatus('error');
      }
    };

    checkStatus();
    const interval = setInterval(checkStatus, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const handleStartEarning = async () => {
    try {
      setIsEarning(true);
      console.log('Starting earning...');
      
      const response = await fetch('/api/earning/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const result = await response.json();
      
      if (!response.ok || !result.success) {
        throw new Error(result.error || 'Failed to start earning');
      }
      
      console.log('Earning started successfully');
    } catch (error: any) {
      console.error('Failed to start earning:', error);
      setIsEarning(false);
      // Show error toast
      if (typeof window !== 'undefined') {
        // Trigger a custom event for toast notification
        window.dispatchEvent(new CustomEvent('showToast', {
          detail: {
            type: 'error',
            title: 'Start Earning Failed',
            message: error.message || 'Failed to start earning'
          }
        }));
      }
    }
  };

  const handleStopEarning = async () => {
    try {
      setIsEarning(false);
      console.log('Stopping earning...');
      
      const response = await fetch('/api/earning/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const result = await response.json();
      
      if (!response.ok || !result.success) {
        throw new Error(result.error || 'Failed to stop earning');
      }
      
      console.log('Earning stopped successfully');
    } catch (error: any) {
      console.error('Failed to stop earning:', error);
      setIsEarning(true);
      // Show error toast
      if (typeof window !== 'undefined') {
        // Trigger a custom event for toast notification
        window.dispatchEvent(new CustomEvent('showToast', {
          detail: {
            type: 'error',
            title: 'Stop Earning Failed',
            message: error.message || 'Failed to stop earning'
          }
        }));
      }
    }
  };
  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center mb-8"
    >
      <div className="flex items-center justify-center gap-4 mb-6">
        {/* AIPG Logo */}
        <div className="relative">
          <img 
            src="/AIPGsimplelogo.png" 
            alt="AI Power Grid" 
            className="w-16 h-16"
            style={{ filter: 'drop-shadow(0 0 15px rgba(255, 107, 53, 0.4))' }}
          />
        </div>
        <div className="text-center">
          <h1 className="text-4xl font-black tracking-tight mb-2">
            <span className="bg-gradient-to-r from-white via-gray-100 to-white bg-clip-text text-transparent">
              AI POWER GRID
            </span>
          </h1>
          <div className="w-24 h-1 bg-gradient-to-r from-transparent via-orange-500 to-transparent mx-auto"></div>
        </div>
      </div>
      
      <div className="max-w-3xl mx-auto">
        <p className="text-xl text-gray-300 mb-2">
          <span className="text-white">Earn Money with Your </span>
          <span className="aipg-gradient-text font-bold glow-text-orange">GPU</span>
        </p>
        <p className="text-base text-gray-400 leading-relaxed mb-4">
          Your graphics card can earn money 24/7 by helping others create AI art and videos. 
          <span className="text-aipg-gold font-semibold"> Set it up once, earn forever.</span>
        </p>
        <div className="flex items-center justify-center gap-4">
          {workerStatus === 'configured' ? (
            <div className="flex items-center gap-4">
              {isEarning ? (
                <div className="inline-flex items-center gap-2 px-4 py-2 bg-green-900/30 rounded-full border border-green-700">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm text-green-300 font-medium">Earning Active</span>
                </div>
              ) : (
                <div className="inline-flex items-center gap-2 px-4 py-2 bg-yellow-900/30 rounded-full border border-yellow-700">
                  <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                  <span className="text-sm text-yellow-300 font-medium">Ready to Earn</span>
                </div>
              )}
              <div className="flex gap-2">
                {!isEarning ? (
                  <button
                    onClick={handleStartEarning}
                    className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-all flex items-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1m4 0h1m-6 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Start Earning
                  </button>
                ) : (
                  <button
                    onClick={handleStopEarning}
                    className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-all flex items-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10h6v4H9z" />
                    </svg>
                    Stop Earning
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900/30 rounded-full border border-gray-700">
              <div className="w-2 h-2 bg-gray-500 rounded-full"></div>
              <span className="text-sm text-gray-300 font-medium">Configure Connection</span>
            </div>
          )}
          <div className="text-sm text-gray-500">
            <span className="font-semibold text-aipg-gold">Step 1:</span> Configure your connection below
          </div>
        </div>
      </div>
    </motion.header>
  );
}
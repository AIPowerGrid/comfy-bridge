'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

interface RebuildingPageProps {
  message?: string;
  onComplete?: () => void;
}

export default function RebuildingPage({ 
  message = "Rebuilding containers...", 
  onComplete 
}: RebuildingPageProps) {
  const [dots, setDots] = useState(1);
  const [status, setStatus] = useState('starting');
  const [progress, setProgress] = useState(0);
  const [elapsedTime, setElapsedTime] = useState(0);
  
  useEffect(() => {
    // Animate dots
    const dotsInterval = setInterval(() => {
      setDots(prev => (prev % 3) + 1);
    }, 500);
    
    // Update elapsed time
    const timeInterval = setInterval(() => {
      setElapsedTime(prev => prev + 1);
    }, 1000);
    
    // Simulate progress stages
    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) return 100;
        // Slower progress as we get closer to 100
        const increment = prev < 30 ? 5 : prev < 60 ? 3 : prev < 90 ? 2 : 1;
        return Math.min(prev + increment, 99); // Never reach 100 automatically
      });
    }, 1500);
    
    // Update status messages based on elapsed time
    const statusTimeout1 = setTimeout(() => setStatus('stopping'), 3000);
    const statusTimeout2 = setTimeout(() => setStatus('building'), 8000);
    const statusTimeout3 = setTimeout(() => setStatus('starting'), 20000);
    const statusTimeout4 = setTimeout(() => setStatus('healthcheck'), 30000);
    
    // After 2 minutes, just force reload - containers should be up by then
    const forceReloadTimer = setTimeout(() => {
      console.log('Forcing page reload after 2 minutes...');
      window.location.reload();
    }, 120000); // 2 minutes
    
    // Start aggressive health checking after 30 seconds
    let checkInterval: NodeJS.Timeout;
    const startChecking = setTimeout(() => {
      console.log('Starting health checks...');
      let consecutiveFailures = 0;
      
      checkInterval = setInterval(async () => {
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 3000);
          
          const response = await fetch('/api/health', {
            method: 'GET',
            cache: 'no-cache',
            signal: controller.signal,
          });
          
          clearTimeout(timeoutId);
          
          if (response.ok) {
            consecutiveFailures = 0;
            setProgress(100);
            setStatus('complete');
            clearInterval(checkInterval);
            clearTimeout(forceReloadTimer);
            
            console.log('Health check successful! Reloading page...');
            // Wait a moment then reload
            setTimeout(() => {
              window.location.reload();
            }, 1500);
          }
        } catch (error) {
          consecutiveFailures++;
          console.log(`Health check failed (${consecutiveFailures} consecutive failures)`);
          // Continue checking - containers might still be starting
        }
      }, 3000);
    }, 30000); // Start checking after 30 seconds
    
    return () => {
      clearInterval(dotsInterval);
      clearInterval(timeInterval);
      clearInterval(progressInterval);
      clearTimeout(statusTimeout1);
      clearTimeout(statusTimeout2);
      clearTimeout(statusTimeout3);
      clearTimeout(statusTimeout4);
      clearTimeout(startChecking);
      clearTimeout(forceReloadTimer);
      if (checkInterval) clearInterval(checkInterval);
    };
  }, []);
  
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  const getStatusMessage = () => {
    switch(status) {
      case 'starting': return 'Initializing rebuild process...';
      case 'stopping': return 'Stopping current containers...';
      case 'building': return 'Building new container images...';
      case 'starting': return 'Starting containers...';
      case 'healthcheck': return 'Performing health checks...';
      case 'complete': return 'Rebuild complete! Redirecting...';
      default: return 'Processing...';
    }
  };
  
  const getStatusColor = () => {
    switch(status) {
      case 'complete': return 'text-green-400';
      case 'healthcheck': return 'text-blue-400';
      default: return 'text-aipg-gold';
    }
  };
  
  return (
    <div className="fixed inset-0 bg-gray-900 flex items-center justify-center z-50">
      <div className="max-w-lg w-full mx-4">
        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-gray-800 rounded-lg p-8 shadow-2xl border border-gray-700"
        >
          {/* Logo/Icon */}
          <div className="flex justify-center mb-6">
            <motion.div
              animate={{ rotate: status === 'complete' ? 0 : 360 }}
              transition={{ 
                duration: status === 'complete' ? 0 : 2, 
                repeat: status === 'complete' ? 0 : Infinity, 
                ease: "linear" 
              }}
              className="w-16 h-16 border-4 border-aipg-gold border-t-transparent rounded-full"
            />
          </div>
          
          {/* Main Message */}
          <h2 className="text-2xl font-bold text-center text-white mb-2">
            {message}{'.'.repeat(dots)}
          </h2>
          
          {/* Status Message */}
          <p className={`text-center mb-6 transition-colors ${getStatusColor()}`}>
            {getStatusMessage()}
          </p>
          
          {/* Progress Bar */}
          <div className="relative w-full h-3 bg-gray-700 rounded-full overflow-hidden mb-4">
            <motion.div
              className="absolute top-0 left-0 h-full bg-gradient-to-r from-aipg-gold to-yellow-500"
              initial={{ width: '0%' }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5 }}
            />
            {/* Shimmer effect */}
            <motion.div
              className="absolute top-0 left-0 h-full w-1/3 bg-gradient-to-r from-transparent via-white/20 to-transparent"
              animate={{ x: ['0%', '300%'] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            />
          </div>
          
          {/* Progress Percentage and Time */}
          <div className="flex justify-between text-sm text-gray-400 mb-6">
            <span>{progress}% Complete</span>
            <span>Elapsed: {formatTime(elapsedTime)}</span>
          </div>
          
          {/* Info Box */}
          <div className="bg-gray-900/50 rounded-lg p-4 border border-gray-700">
            <h3 className="text-sm font-semibold text-aipg-gold mb-2">What's happening?</h3>
            <ul className="text-xs text-gray-400 space-y-1">
              <li className={status === 'stopping' || progress > 10 ? 'text-green-400' : ''}>
                ✓ Saving configuration changes
              </li>
              <li className={progress > 20 ? 'text-green-400' : ''}>
                ✓ Stopping existing containers
              </li>
              <li className={progress > 40 ? 'text-green-400' : ''}>
                {progress > 40 ? '✓' : '○'} Rebuilding Docker images
              </li>
              <li className={progress > 70 ? 'text-green-400' : ''}>
                {progress > 70 ? '✓' : '○'} Starting new containers
              </li>
              <li className={progress >= 100 ? 'text-green-400' : ''}>
                {progress >= 100 ? '✓' : '○'} Verifying health status
              </li>
            </ul>
          </div>
          
          {/* Warning */}
          <p className="text-xs text-gray-500 text-center mt-4">
            Please do not close this window. This process typically takes 1-3 minutes.
          </p>
          
          {/* Status Icon for completion */}
          {status === 'complete' && (
            <motion.div
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex justify-center mt-4"
            >
              <div className="text-green-400 text-4xl">✓</div>
            </motion.div>
          )}
        </motion.div>
      </div>
    </div>
  );
}

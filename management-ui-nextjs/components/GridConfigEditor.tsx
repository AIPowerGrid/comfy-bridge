'use client';

import { motion } from 'framer-motion';
import { useState, useEffect } from 'react';

interface GridConfigEditorProps {
  gridApiKey: string;
  workerName: string;
  aipgWallet: string;
  onSave: (config: { gridApiKey: string; workerName: string; aipgWallet: string }) => Promise<void>;
}

export default function GridConfigEditor({ 
  gridApiKey, 
  workerName, 
  aipgWallet, 
  onSave 
}: GridConfigEditorProps) {
  const [localGridApiKey, setLocalGridApiKey] = useState(gridApiKey);
  const [localWorkerName, setLocalWorkerName] = useState(workerName);
  const [localAipgWallet, setLocalAipgWallet] = useState(aipgWallet);
  const [saving, setSaving] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [testingToken, setTestingToken] = useState(false);
  const [tokenValid, setTokenValid] = useState(false);
  const [lastValidatedKey, setLastValidatedKey] = useState('');

  const hasChanges = 
    localGridApiKey !== gridApiKey || 
    localWorkerName !== workerName || 
    localAipgWallet !== aipgWallet;

  const isComplete = localGridApiKey && localWorkerName && localAipgWallet;

  // Reset validation when API key changes
  useEffect(() => {
    if (localGridApiKey !== lastValidatedKey) {
      setTokenValid(false);
    }
  }, [localGridApiKey, lastValidatedKey]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({
        gridApiKey: localGridApiKey,
        workerName: localWorkerName,
        aipgWallet: localAipgWallet,
      });
    } catch (error) {
      console.error('Failed to save grid config:', error);
    } finally {
      setSaving(false);
    }
  };

  const testToken = async () => {
    if (!localGridApiKey) return;
    
    // Skip validation if we already validated this exact key
    if (lastValidatedKey === localGridApiKey && tokenValid) {
      return;
    }
    
    setTestingToken(true);
    try {
      // Test the token by making a simple API call
      const response = await fetch('/api/grid-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          gridApiKey: localGridApiKey,
          workerName: localWorkerName,
          aipgWallet: localAipgWallet,
          testOnly: true 
        }),
      });
      
      if (response.ok) {
        setTokenValid(true);
        setLastValidatedKey(localGridApiKey);
      } else {
        setTokenValid(false);
        setLastValidatedKey('');
      }
    } catch (error) {
      setTokenValid(false);
      setLastValidatedKey('');
    } finally {
      setTestingToken(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-900 rounded-xl border border-gray-700"
    >
      {/* Collapsible Header */}
      <div 
        className="flex items-center justify-between p-6 cursor-pointer hover:bg-gray-800/30 transition-colors"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-3">
          <svg className="w-8 h-8 text-aipg-orange" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
          </svg>
          <div>
            <h3 className="text-2xl font-bold text-white">Grid Configuration</h3>
            <p className="text-sm text-gray-400">
              {isComplete ? '✓ Configuration complete' : 'Configure your AI Power Grid connection to start earning'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isComplete && (
            <span className="px-3 py-1 text-xs bg-green-500/20 text-green-400 rounded-full border border-green-500/50">
              Complete
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
          {/* Grid API Key */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              AI Power Grid API Key
              <span className="text-red-400 ml-1">*</span>
            </label>
            <div className="relative">
              <input
                type={showApiKey ? "text" : "password"}
                value={localGridApiKey}
                onChange={(e) => {
                  setLocalGridApiKey(e.target.value);
                  setTokenValid(false); // Reset validation when key changes
                }}
                placeholder="Enter your Grid API key"
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-aipg-orange transition-colors pr-32"
              />
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2">
                {localGridApiKey && (
                  <button
                    type="button"
                    onClick={testToken}
                    disabled={testingToken}
                    className={`px-3 py-1 text-xs font-medium rounded transition-all ${
                      tokenValid 
                        ? 'bg-green-600 text-white' 
                        : testingToken
                        ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                        : 'bg-aipg-orange hover:bg-orange-600 text-white'
                    }`}
                  >
                    {testingToken ? 'Testing...' : tokenValid ? '✓ Valid' : 'Confirm'}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="px-3 py-1 text-xs text-gray-400 hover:text-white transition-colors"
                >
                  {showApiKey ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>
            <div className="mt-2 flex items-center gap-2 text-xs text-gray-400">
              <span>Don't have an API key?</span>
              <a 
                href="https://dashboard.aipowergrid.io" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-aipg-orange hover:text-aipg-gold transition-colors"
              >
                Get New Key →
              </a>
            </div>
          </div>

          {/* Progressive Disclosure - Only show if API key is valid */}
          {tokenValid && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              transition={{ duration: 0.3 }}
              className="space-y-4"
            >
              {/* Worker Name */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Worker Name
                  <span className="text-red-400 ml-1">*</span>
                </label>
                <input
                  type="text"
                  value={localWorkerName}
                  onChange={(e) => setLocalWorkerName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                  placeholder="e.g., austin-powers-01"
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-aipg-orange transition-colors"
                />
                <p className="mt-1 text-xs text-gray-400">Use lowercase letters, numbers, and hyphens only</p>
              </div>

              {/* AIPG Wallet */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  AIPG Wallet Address
                  <span className="text-red-400 ml-1">*</span>
                </label>
                <input
                  type="text"
                  value={localAipgWallet}
                  onChange={(e) => setLocalAipgWallet(e.target.value)}
                  placeholder="e.g., AdD3DPyBpd2pgoAQD59EwZLniVwmC6Gfj9"
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-aipg-orange transition-colors"
                />
                <p className="mt-1 text-xs text-gray-400">Your AIPG wallet address where earnings will be sent</p>
              </div>

              {/* Full Worker Name Preview */}
              {localWorkerName && localAipgWallet && (
                <div className="bg-blue-900/20 border border-blue-500/30 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-1">Full Worker Name:</p>
                  <p className="text-sm font-mono text-blue-400">{localWorkerName}.{localAipgWallet}</p>
                </div>
              )}

              {/* Save Button */}
              <button
                onClick={handleSave}
                disabled={!hasChanges || saving || !localWorkerName || !localAipgWallet}
                className={`w-full py-3 rounded-lg font-bold transition-all ${
                  hasChanges && localWorkerName && localAipgWallet && !saving
                    ? 'aipg-button text-white'
                    : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                }`}
              >
                {saving ? 'Saving...' : hasChanges ? 'Save Configuration' : 'No Changes'}
              </button>
            </motion.div>
          )}

          {/* Status Message */}
          {!localGridApiKey ? (
            <div className="bg-yellow-900/20 border border-yellow-500/30 rounded-lg p-3">
              <p className="text-xs text-yellow-400">
                ⚠️ Enter your API key to continue configuration
              </p>
            </div>
          ) : !tokenValid ? (
            <div className="bg-orange-900/20 border border-orange-500/30 rounded-lg p-3">
              <p className="text-xs text-orange-400">
                🔑 Click "Confirm" to validate your API key
              </p>
            </div>
          ) : !isComplete ? (
            <div className="bg-blue-900/20 border border-blue-500/30 rounded-lg p-3">
              <p className="text-xs text-blue-400">
                📝 Complete the remaining fields to finish configuration
              </p>
            </div>
          ) : (
            <div className="bg-green-900/20 border border-green-500/30 rounded-lg p-3">
              <p className="text-xs text-green-400">
                ✓ Configuration complete! Select and download models below to start earning
              </p>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}


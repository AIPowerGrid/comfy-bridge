'use client';

import { motion } from 'framer-motion';

interface APIKeyStatusProps {
  hasHuggingFaceKey: boolean;
  hasCivitaiKey: boolean;
  modelsRequiringKeys: {
    huggingface: number;
    civitai: number;
  };
}

export default function APIKeyStatus({ hasHuggingFaceKey, hasCivitaiKey, modelsRequiringKeys }: APIKeyStatusProps) {
  const needsKeys = (!hasHuggingFaceKey && modelsRequiringKeys.huggingface > 0) || 
                    (!hasCivitaiKey && modelsRequiringKeys.civitai > 0);
  
  if (!needsKeys) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-effect rounded-xl p-4 border border-yellow-500/30 bg-yellow-500/10 mb-6"
    >
      <div className="flex items-start gap-3">
        <div className="text-yellow-500 text-2xl">⚠️</div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-yellow-400 mb-2">API Keys Required</h3>
          <p className="text-sm text-gray-300 mb-3">
            Some models require API keys for downloading. Configure these in your <code className="bg-black/30 px-2 py-1 rounded text-aipg-orange">.env</code> file:
          </p>
          
          <div className="space-y-2">
            {!hasHuggingFaceKey && modelsRequiringKeys.huggingface > 0 && (
              <div className="flex items-center gap-2 text-sm">
                <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded font-mono text-xs">
                  HUGGING_FACE_API_KEY
                </span>
                <span className="text-gray-400">
                  • {modelsRequiringKeys.huggingface} model{modelsRequiringKeys.huggingface !== 1 ? 's' : ''} require this
                </span>
                <a 
                  href="https://huggingface.co/settings/tokens" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-aipg-orange hover:text-aipg-gold transition-colors underline ml-auto"
                >
                  Get Key →
                </a>
              </div>
            )}
            
            {!hasCivitaiKey && modelsRequiringKeys.civitai > 0 && (
              <div className="flex items-center gap-2 text-sm">
                <span className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded font-mono text-xs">
                  CIVITAI_API_KEY
                </span>
                <span className="text-gray-400">
                  • {modelsRequiringKeys.civitai} model{modelsRequiringKeys.civitai !== 1 ? 's' : ''} require this
                </span>
                <a 
                  href="https://civitai.com/user/account" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-aipg-orange hover:text-aipg-gold transition-colors underline ml-auto"
                >
                  Get Key →
                </a>
              </div>
            )}
          </div>
          
          <div className="mt-3 pt-3 border-t border-yellow-500/20">
            <a 
              href="https://github.com/yourusername/comfy-bridge/blob/main/DOCKER.md#api-keys" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-xs text-gray-400 hover:text-aipg-orange transition-colors flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              View Documentation for Setup Instructions
            </a>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

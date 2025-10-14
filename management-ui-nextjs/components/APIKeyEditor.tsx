'use client';

import { motion } from 'framer-motion';
import { useState } from 'react';

interface APIKeyEditorProps {
  huggingfaceKey: string;
  civitaiKey: string;
  onSave: (keys: { huggingface: string; civitai: string }) => Promise<void>;
}

export default function APIKeyEditor({ huggingfaceKey, civitaiKey, onSave }: APIKeyEditorProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [showHF, setShowHF] = useState(false);
  const [showCivitai, setShowCivitai] = useState(false);
  const [hfKey, setHfKey] = useState(huggingfaceKey);
  const [civKey, setCivKey] = useState(civitaiKey);
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verificationStatus, setVerificationStatus] = useState<{hf?: boolean, civitai?: boolean}>({});
  const [lastValidatedKeys, setLastValidatedKeys] = useState<{hf?: string, civitai?: string}>({});

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({ huggingface: hfKey, civitai: civKey });
      setIsEditing(false);
      setShowHF(false);
      setShowCivitai(false);
    } catch (error) {
      console.error('Failed to save API keys:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setHfKey(huggingfaceKey);
    setCivKey(civitaiKey);
    setIsEditing(false);
    setShowHF(false);
    setShowCivitai(false);
  };

  const verifyKeys = async () => {
    setVerifying(true);
    try {
      // Test HuggingFace key - only if it changed
      if (hfKey && hfKey !== lastValidatedKeys.hf) {
        try {
          const hfResponse = await fetch('/api/api-keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              huggingface: hfKey, 
              civitai: civKey,
              testOnly: true 
            }),
          });
          const isValid = hfResponse.ok;
          setVerificationStatus(prev => ({ ...prev, hf: isValid }));
          if (isValid) {
            setLastValidatedKeys(prev => ({ ...prev, hf: hfKey }));
          }
        } catch {
          setVerificationStatus(prev => ({ ...prev, hf: false }));
        }
      } else if (hfKey === lastValidatedKeys.hf && verificationStatus.hf) {
        // Key hasn't changed and was previously valid, keep status
        setVerificationStatus(prev => ({ ...prev, hf: true }));
      }

      // Test Civitai key - only if it changed
      if (civKey && civKey !== lastValidatedKeys.civitai) {
        try {
          const civResponse = await fetch('/api/api-keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              huggingface: hfKey, 
              civitai: civKey,
              testOnly: true 
            }),
          });
          const isValid = civResponse.ok;
          setVerificationStatus(prev => ({ ...prev, civitai: isValid }));
          if (isValid) {
            setLastValidatedKeys(prev => ({ ...prev, civitai: civKey }));
          }
        } catch {
          setVerificationStatus(prev => ({ ...prev, civitai: false }));
        }
      } else if (civKey === lastValidatedKeys.civitai && verificationStatus.civitai) {
        // Key hasn't changed and was previously valid, keep status
        setVerificationStatus(prev => ({ ...prev, civitai: true }));
      }
    } finally {
      setVerifying(false);
    }
  };

  const hasKeys = huggingfaceKey || civitaiKey;

  const maskKey = (key: string) => {
    if (!key || key.length < 8) return '••••••••';
    return key.substring(0, 4) + '•'.repeat(Math.max(8, key.length - 8)) + key.substring(key.length - 4);
  };

  return (
    <div className="space-y-4">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-gray-400">
              Some AI models require API keys to download. Don't worry - these are free to get!
            </p>
            {!isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                className="px-4 py-2 rounded-lg font-semibold text-sm bg-aipg-orange/20 text-aipg-orange hover:bg-aipg-orange/30 border border-aipg-orange/50 transition-all"
              >
                Edit Keys
              </button>
            )}
          </div>

          <div className="space-y-4">
            {/* HuggingFace API Key */}
            <div>
              <label className="block text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
                <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs">
                  HUGGING_FACE_API_KEY <span className="text-red-400">*</span>
                </span>
                <a 
                  href="https://huggingface.co/settings/tokens" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-xs text-aipg-orange hover:text-aipg-gold transition-colors underline"
                >
                  Get New Key →
                </a>
              </label>
              <div className="flex gap-2">
                <div className="flex-1 relative">
                  <input
                    type={showHF ? 'text' : 'password'}
                    value={isEditing ? hfKey : maskKey(huggingfaceKey)}
                    onChange={(e) => setHfKey(e.target.value)}
                    disabled={!isEditing}
                    placeholder="hf_••••••••••••••••"
                    className="w-full bg-aipg-darkGray border border-white/10 rounded-lg px-4 py-2 text-white font-mono text-sm focus:border-aipg-orange/50 focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed"
                  />
                  {isEditing && hfKey && (
                    <button
                      onClick={() => setShowHF(!showHF)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                      title={showHF ? 'Hide' : 'Show'}
                    >
                      {showHF ? (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      )}
                    </button>
                  )}
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-1">Required for downloading models from HuggingFace</p>
            </div>

            {/* Civitai API Key */}
            <div>
              <label className="block text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
                <span className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">
                  CIVITAI_API_KEY <span className="text-red-400">*</span>
                </span>
                <a 
                  href="https://civitai.com/user/account" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-xs text-aipg-orange hover:text-aipg-gold transition-colors underline"
                >
                  Get New Key →
                </a>
              </label>
              <div className="flex gap-2">
                <div className="flex-1 relative">
                  <input
                    type={showCivitai ? 'text' : 'password'}
                    value={isEditing ? civKey : maskKey(civitaiKey)}
                    onChange={(e) => setCivKey(e.target.value)}
                    disabled={!isEditing}
                    placeholder="••••••••••••••••"
                    className="w-full bg-aipg-darkGray border border-white/10 rounded-lg px-4 py-2 text-white font-mono text-sm focus:border-aipg-orange/50 focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed"
                  />
                  {isEditing && civKey && (
                    <button
                      onClick={() => setShowCivitai(!showCivitai)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                      title={showCivitai ? 'Hide' : 'Show'}
                    >
                      {showCivitai ? (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      )}
                    </button>
                  )}
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-1">Required for downloading models from Civitai</p>
            </div>

            {/* Action Buttons */}
            {isEditing && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="flex gap-3 pt-2"
              >
                <button
                  onClick={handleCancel}
                  className="flex-1 px-4 py-2 rounded-lg font-semibold text-sm border-2 border-white/20 text-white hover:bg-white/10 transition-all"
                >
                  Cancel
                </button>
                <button
                  onClick={verifyKeys}
                  disabled={verifying || (!hfKey && !civKey) || (hfKey === lastValidatedKeys.hf && civKey === lastValidatedKeys.civitai && verificationStatus.hf && verificationStatus.civitai)}
                  className="px-4 py-2 rounded-lg font-semibold text-sm bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {verifying ? 'Verifying...' : 
                   (hfKey === lastValidatedKeys.hf && civKey === lastValidatedKeys.civitai && verificationStatus.hf && verificationStatus.civitai) ? '✓ Verified' : 'Verify'}
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex-1 px-4 py-2 rounded-lg font-semibold text-sm bg-gradient-to-r from-aipg-orange to-aipg-gold text-white hover:shadow-lg hover:shadow-aipg-orange/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? 'Saving...' : 'Save Keys'}
                </button>
              </motion.div>
            )}

            {/* Verification Status */}
            {(verificationStatus.hf !== undefined || verificationStatus.civitai !== undefined) && (
              <div className="space-y-2">
                {verificationStatus.hf !== undefined && (
                  <div className={`px-3 py-2 rounded-lg text-sm ${
                    verificationStatus.hf 
                      ? 'bg-green-500/20 text-green-400 border border-green-500/50' 
                      : 'bg-red-500/20 text-red-400 border border-red-500/50'
                  }`}>
                    {verificationStatus.hf ? '✓' : '✗'} HuggingFace API key {verificationStatus.hf ? 'valid' : 'invalid'}
                  </div>
                )}
                {verificationStatus.civitai !== undefined && (
                  <div className={`px-3 py-2 rounded-lg text-sm ${
                    verificationStatus.civitai 
                      ? 'bg-green-500/20 text-green-400 border border-green-500/50' 
                      : 'bg-red-500/20 text-red-400 border border-red-500/50'
                  }`}>
                    {verificationStatus.civitai ? '✓' : '✗'} Civitai API key {verificationStatus.civitai ? 'valid' : 'invalid'}
                  </div>
                )}
              </div>
            )}

            {/* Documentation Link */}
            <div className="pt-3 border-t border-white/10">
              <a 
                href="https://github.com/yourusername/comfy-bridge/blob/main/DOCKER.md#api-keys" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-xs text-gray-400 hover:text-aipg-orange transition-colors flex items-center gap-1"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                View Setup Documentation
              </a>
            </div>
          </div>
    </div>
  );
}
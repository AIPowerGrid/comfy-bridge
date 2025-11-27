'use client';

import { motion, AnimatePresence } from 'framer-motion';

interface GettingStartedGuideProps {
  onClose: () => void;
}

export default function GettingStartedGuide({ onClose }: GettingStartedGuideProps) {
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          className="bg-gray-900 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-gray-700"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="sticky top-0 bg-gray-900 border-b border-gray-700 p-6 rounded-t-2xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <img src="/AIPGsimplelogo.png" alt="AI Power Grid" className="w-8 h-8" />
                <h1 className="text-2xl font-bold">Welcome to AI Power Grid</h1>
              </div>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="p-6 space-y-8">
            
            {/* What is AI Power Grid */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">1</span>
                Turn Your GPU Into Money
              </h2>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                <p className="text-gray-300 leading-relaxed">
                  Your graphics card can earn money by helping others create AI art and videos. 
                  <span className="text-aipg-gold font-semibold"> No technical skills needed - just set it up and let it run!</span>
                </p>
              </div>
            </section>

            {/* How it Works */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">2</span>
                How Does It Work?
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-gray-800 rounded-lg p-4 border border-gray-600 text-center">
                  <div className="w-12 h-12 bg-aipg-orange rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                    </svg>
                  </div>
                  <h3 className="font-semibold mb-2">1. Choose Models</h3>
                  <p className="text-sm text-gray-400">Select AI models that match your computer's capabilities</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 border border-gray-600 text-center">
                  <div className="w-12 h-12 bg-aipg-orange rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                  </div>
                  <h3 className="font-semibold mb-2">2. Download & Install</h3>
                  <p className="text-sm text-gray-400">We'll download the models automatically to your computer</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 border border-gray-600 text-center">
                  <div className="w-12 h-12 bg-aipg-orange rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                    </svg>
                  </div>
                  <h3 className="font-semibold mb-2">3. Earn Rewards</h3>
                  <p className="text-sm text-gray-400">Get paid when others use your AI models to create content</p>
                </div>
              </div>
            </section>

            {/* Your Computer Setup */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">3</span>
                Your Computer Setup
              </h2>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                <p className="text-gray-300 mb-4">
                  We've detected your computer's capabilities. Here's what you can run:
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-green-900/30 border border-green-700 rounded-lg p-3">
                    <h4 className="font-semibold text-green-400 mb-2">✅ What You Can Run</h4>
                    <ul className="text-sm text-gray-300 space-y-1">
                      <li>• Text-to-Image models (create pictures from descriptions)</li>
                      <li>• Text-to-Video models (create videos from descriptions)</li>
                      <li>• Image-to-Video models (animate static images)</li>
                      <li>• High-quality, professional AI models</li>
                    </ul>
                  </div>
                  <div className="bg-blue-900/30 border border-blue-700 rounded-lg p-3">
                    <h4 className="font-semibold text-blue-400 mb-2">💡 Pro Tip</h4>
                    <p className="text-sm text-gray-300">
                      The more powerful your graphics card, the more advanced models you can run, 
                      and the more you can earn!
                    </p>
                  </div>
                </div>
              </div>
            </section>

            {/* Model Types Explained */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">4</span>
                Understanding Model Types
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                  <h4 className="font-semibold text-aipg-orange mb-2">🎨 Text-to-Image</h4>
                  <p className="text-sm text-gray-300 mb-2">Create pictures from text descriptions</p>
                  <p className="text-xs text-gray-400">Example: "A cat wearing a space helmet" → AI-generated image</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                  <h4 className="font-semibold text-aipg-orange mb-2">🎬 Text-to-Video</h4>
                  <p className="text-sm text-gray-300 mb-2">Create videos from text descriptions</p>
                  <p className="text-xs text-gray-400">Example: "A sunset over mountains" → AI-generated video</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                  <h4 className="font-semibold text-aipg-orange mb-2">🔄 Image-to-Video</h4>
                  <p className="text-sm text-gray-300 mb-2">Animate static images into videos</p>
                  <p className="text-xs text-gray-400">Example: Still photo → Animated video</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                  <h4 className="font-semibold text-aipg-orange mb-2">🎯 Image-to-Image</h4>
                  <p className="text-sm text-gray-300 mb-2">Transform existing images</p>
                  <p className="text-xs text-gray-400">Example: Photo → Artistic painting style</p>
                </div>
              </div>
            </section>

            {/* Getting Started Steps */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">5</span>
                Ready to Start?
              </h2>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-green-600 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">1</span>
                    <div>
                      <h4 className="font-semibold">Configure Grid Connection</h4>
                      <p className="text-sm text-gray-400">Enter your Grid API key, worker name, and AIPG wallet address to connect to the network</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-green-600 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">2</span>
                    <div>
                      <h4 className="font-semibold">Set up API Keys</h4>
                      <p className="text-sm text-gray-400">Get free API keys from HuggingFace and Civitai to download models</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-green-600 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">3</span>
                    <div>
                      <h4 className="font-semibold">Choose Your Models</h4>
                      <p className="text-sm text-gray-400">Pick models compatible with your GPU and click "Download & Host"</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-green-600 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">4</span>
                    <div>
                      <h4 className="font-semibold">Start Earning!</h4>
                      <p className="text-sm text-gray-400">Your worker automatically accepts jobs and earns AIPG tokens - no further action needed!</p>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* Footer */}
            <div className="text-center pt-4 border-t border-gray-700">
              <button
                onClick={onClose}
                className="px-8 py-3 bg-aipg-orange text-white rounded-lg font-semibold hover:bg-aipg-orange/90 transition-all"
              >
                Let's Get Started!
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

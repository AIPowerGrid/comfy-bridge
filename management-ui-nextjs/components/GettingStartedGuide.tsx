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
                What is AI Power Grid?
              </h2>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                <p className="text-gray-300 leading-relaxed mb-3">
                  AI Power Grid is a <span className="text-aipg-gold font-semibold">decentralized AI compute network</span> that 
                  connects people who need AI image and video generation with GPU owners who can provide that computing power.
                </p>
                <p className="text-gray-300 leading-relaxed">
                  By running this worker, your GPU processes AI generation requests and you earn 
                  <span className="text-aipg-gold font-semibold"> AIPG tokens</span> for every job completed!
                </p>
              </div>
            </section>

            {/* How it Works */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">2</span>
                How Does It Work?
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-gray-800 rounded-lg p-4 border border-gray-600 text-center">
                  <div className="w-12 h-12 bg-aipg-orange rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  </div>
                  <h3 className="font-semibold mb-2">1. Configure</h3>
                  <p className="text-sm text-gray-400">Set up your Grid API key and wallet address</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 border border-gray-600 text-center">
                  <div className="w-12 h-12 bg-aipg-orange rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                  </div>
                  <h3 className="font-semibold mb-2">2. Download</h3>
                  <p className="text-sm text-gray-400">Install AI models compatible with your GPU</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 border border-gray-600 text-center">
                  <div className="w-12 h-12 bg-aipg-orange rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <h3 className="font-semibold mb-2">3. Start Hosting</h3>
                  <p className="text-sm text-gray-400">Enable models to start accepting jobs</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 border border-gray-600 text-center">
                  <div className="w-12 h-12 bg-aipg-orange rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                    </svg>
                  </div>
                  <h3 className="font-semibold mb-2">4. Earn AIPG</h3>
                  <p className="text-sm text-gray-400">Get paid for every job your GPU completes</p>
                </div>
              </div>
            </section>

            {/* Model Types Explained */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">3</span>
                Model Types
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gray-800 rounded-lg p-4 border border-blue-600/50">
                  <h4 className="font-semibold text-blue-400 mb-2 flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-blue-500/20 text-blue-300 rounded text-xs">Image</span>
                    Text-to-Image
                  </h4>
                  <p className="text-sm text-gray-300 mb-2">Generate images from text descriptions</p>
                  <p className="text-xs text-gray-500">Models: FLUX, SDXL, Stable Diffusion</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 border border-purple-600/50">
                  <h4 className="font-semibold text-purple-400 mb-2 flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded text-xs">Video</span>
                    Text-to-Video
                  </h4>
                  <p className="text-sm text-gray-300 mb-2">Generate videos from text descriptions</p>
                  <p className="text-xs text-gray-500">Models: WAN 2.2, LTX-Video</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 border border-green-600/50">
                  <h4 className="font-semibold text-green-400 mb-2 flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-green-500/20 text-green-300 rounded text-xs">Video</span>
                    Image-to-Video
                  </h4>
                  <p className="text-sm text-gray-300 mb-2">Animate static images into videos</p>
                  <p className="text-xs text-gray-500">Models: WAN 2.2 I2V</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 border border-orange-600/50">
                  <h4 className="font-semibold text-orange-400 mb-2 flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-orange-500/20 text-orange-300 rounded text-xs">Image</span>
                    Image-to-Image
                  </h4>
                  <p className="text-sm text-gray-300 mb-2">Transform and edit existing images</p>
                  <p className="text-xs text-gray-500">Models: FLUX Kontext, ControlNet</p>
                </div>
              </div>
            </section>

            {/* GPU Requirements */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">4</span>
                GPU Requirements
              </h2>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-3">
                    <h4 className="font-semibold text-yellow-400 mb-2">8-12 GB VRAM</h4>
                    <p className="text-sm text-gray-300 mb-2">Entry Level</p>
                    <ul className="text-xs text-gray-400 space-y-1">
                      <li>• SDXL models</li>
                      <li>• Some FLUX models</li>
                      <li>• Basic image generation</li>
                    </ul>
                  </div>
                  <div className="bg-blue-900/20 border border-blue-700/50 rounded-lg p-3">
                    <h4 className="font-semibold text-blue-400 mb-2">16-24 GB VRAM</h4>
                    <p className="text-sm text-gray-300 mb-2">Recommended</p>
                    <ul className="text-xs text-gray-400 space-y-1">
                      <li>• All FLUX models</li>
                      <li>• LTX-Video</li>
                      <li>• Video generation</li>
                    </ul>
                  </div>
                  <div className="bg-green-900/20 border border-green-700/50 rounded-lg p-3">
                    <h4 className="font-semibold text-green-400 mb-2">24+ GB VRAM</h4>
                    <p className="text-sm text-gray-300 mb-2">Premium</p>
                    <ul className="text-xs text-gray-400 space-y-1">
                      <li>• WAN 2.2 14B models</li>
                      <li>• High-quality video</li>
                      <li>• Multiple models</li>
                    </ul>
                  </div>
                </div>
              </div>
            </section>

            {/* Quick Start Steps */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">5</span>
                Quick Start Guide
              </h2>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-green-600 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">1</span>
                    <div>
                      <h4 className="font-semibold">Get Your Grid API Key</h4>
                      <p className="text-sm text-gray-400">
                        Visit <a href="https://dashboard.aipowergrid.io" target="_blank" rel="noopener noreferrer" className="text-aipg-orange hover:underline">dashboard.aipowergrid.io</a> to 
                        create an account and get your API key
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-green-600 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">2</span>
                    <div>
                      <h4 className="font-semibold">Configure Grid Connection</h4>
                      <p className="text-sm text-gray-400">Enter your Grid API key, worker name, and AIPG wallet address in the Grid Configuration section</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-green-600 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">3</span>
                    <div>
                      <h4 className="font-semibold">Set Up API Keys (Free)</h4>
                      <p className="text-sm text-gray-400">
                        Get free API keys from <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener noreferrer" className="text-aipg-orange hover:underline">HuggingFace</a> and 
                        <a href="https://civitai.com/user/account" target="_blank" rel="noopener noreferrer" className="text-aipg-orange hover:underline ml-1">Civitai</a> to download models
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-green-600 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">4</span>
                    <div>
                      <h4 className="font-semibold">Download Models</h4>
                      <p className="text-sm text-gray-400">Browse the Model Registry, select models compatible with your GPU, and click "Start Hosting" to download and enable</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-green-600 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">5</span>
                    <div>
                      <h4 className="font-semibold">Start Earning!</h4>
                      <p className="text-sm text-gray-400">Once models are hosted, your worker automatically accepts jobs and earns AIPG tokens - check your earnings on the dashboard!</p>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* Tips */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">💡</span>
                Pro Tips
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-blue-900/20 border border-blue-700/50 rounded-lg p-3">
                  <h4 className="font-semibold text-blue-400 mb-2">Host Multiple Models</h4>
                  <p className="text-sm text-gray-300">You can host multiple models at once to receive more job types and increase earnings</p>
                </div>
                <div className="bg-purple-900/20 border border-purple-700/50 rounded-lg p-3">
                  <h4 className="font-semibold text-purple-400 mb-2">Video Models Pay More</h4>
                  <p className="text-sm text-gray-300">Video generation jobs typically pay more than image jobs due to higher compute requirements</p>
                </div>
                <div className="bg-green-900/20 border border-green-700/50 rounded-lg p-3">
                  <h4 className="font-semibold text-green-400 mb-2">Keep It Running</h4>
                  <p className="text-sm text-gray-300">Leave your worker running 24/7 to maximize earnings - jobs come in at all hours</p>
                </div>
                <div className="bg-orange-900/20 border border-orange-700/50 rounded-lg p-3">
                  <h4 className="font-semibold text-orange-400 mb-2">Check Compatibility</h4>
                  <p className="text-sm text-gray-300">Models show VRAM requirements - only install models your GPU can handle</p>
                </div>
              </div>
            </section>

            {/* Troubleshooting */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">🔧</span>
                Troubleshooting
              </h2>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                <div className="space-y-3">
                  <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-3">
                    <h4 className="font-semibold text-red-400 mb-2">Build or TypeScript Errors?</h4>
                    <p className="text-sm text-gray-300 mb-2">If you see errors about missing modules or TypeScript types, run:</p>
                    <code className="block bg-gray-900 text-green-400 p-2 rounded text-sm font-mono">
                      cd management-ui-nextjs && npm install
                    </code>
                    <p className="text-xs text-gray-500 mt-2">This installs all required dependencies and type definitions.</p>
                  </div>
                  <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-3">
                    <h4 className="font-semibold text-yellow-400 mb-2">Worker Not Starting?</h4>
                    <p className="text-sm text-gray-300">Make sure Docker Desktop is running and check logs with: <code className="text-green-400 font-mono">docker-compose logs -f</code></p>
                  </div>
                  <div className="bg-blue-900/20 border border-blue-700/50 rounded-lg p-3">
                    <h4 className="font-semibold text-blue-400 mb-2">Not Receiving Jobs?</h4>
                    <p className="text-sm text-gray-300">Verify models show "Hosting" status, your API key is valid, and worker name format is correct (Name.WalletAddress)</p>
                  </div>
                </div>
              </div>
            </section>

            {/* Links */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-aipg-orange rounded-full flex items-center justify-center text-sm font-bold">🔗</span>
                Useful Links
              </h2>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-600">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <a href="https://dashboard.aipowergrid.io" target="_blank" rel="noopener noreferrer" 
                     className="flex items-center gap-2 text-aipg-orange hover:text-aipg-gold transition-colors">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    Worker Dashboard
                  </a>
                  <a href="https://aipowergrid.io" target="_blank" rel="noopener noreferrer"
                     className="flex items-center gap-2 text-aipg-orange hover:text-aipg-gold transition-colors">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                    </svg>
                    AI Power Grid Website
                  </a>
                  <a href="https://discord.gg/aipowergrid" target="_blank" rel="noopener noreferrer"
                     className="flex items-center gap-2 text-aipg-orange hover:text-aipg-gold transition-colors">
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
                    </svg>
                    Join Discord Community
                  </a>
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
              <p className="text-sm text-gray-500 mt-3">
                Need help? Join our Discord community for support!
              </p>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

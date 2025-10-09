'use client';

import { motion } from 'framer-motion';

export default function Header() {
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
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-green-900/30 rounded-full border border-green-700">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm text-green-300 font-medium">Ready to Earn</span>
          </div>
          <div className="text-sm text-gray-500">
            <span className="font-semibold text-aipg-gold">Step 1:</span> Configure your connection below
          </div>
        </div>
      </div>
    </motion.header>
  );
}
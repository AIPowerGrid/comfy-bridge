'use client';

import { WagmiProvider, http } from 'wagmi';
import { base, baseSepolia } from 'wagmi/chains';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getDefaultConfig, RainbowKitProvider } from '@rainbow-me/rainbowkit';
import '@rainbow-me/rainbowkit/styles.css';
import { ReactNode } from 'react';
import { useAccount, useChainId, useSwitchChain } from 'wagmi';
import { useState, useCallback, useEffect } from 'react';
import { ModelType } from './types';
const queryClient = new QueryClient();

const config = getDefaultConfig({
  appName: 'AI Power Grid Model Manager',
  projectId: process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || 'default-project-id',
  chains: [base, baseSepolia],
  transports: {
    [base.id]: http(),
    [baseSepolia.id]: http(),
  },
});

// Web3Provider component
export function Web3Provider({ children }: { children: ReactNode }) {
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitProvider>
          {children}
        </RainbowKitProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}

// useWallet hook
export function useWallet() {
  const { address, isConnected } = useAccount();
  const chainId = useChainId();
  const { switchChain } = useSwitchChain();
  
  const BASE_CHAIN_ID = 8453; // Base mainnet
  const BASE_SEPOLIA_CHAIN_ID = 84532; // Base Sepolia
  
  const isCorrectChain = chainId === BASE_CHAIN_ID || chainId === BASE_SEPOLIA_CHAIN_ID;
  
  const switchToBase = useCallback(() => {
    if (!isCorrectChain) {
      switchChain({ chainId: BASE_CHAIN_ID });
    }
  }, [isCorrectChain, switchChain]);
  
  return {
    isConnected,
    address,
    chainId,
    isCorrectChain,
    switchToBase,
  };
}

// Model info interface
export interface ModelInfo {
  displayName?: string;
  fileName: string;
  description?: string;
  baseModel?: string;
  modelType: ModelType;
  sizeBytes: number;
  isNSFW?: boolean;
}

export interface ModelWithDetails {
  hash: string;
  info: ModelInfo | null;
}

// useModelVault hook
export function useModelVault() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [modelsWithDetails, setModelsWithDetails] = useState<ModelWithDetails[]>([]);
  
  const fetchModels = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // TODO: Replace with actual API call to fetch models from blockchain
      // For now, return empty array to prevent build errors
      setModelsWithDetails([]);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch models'));
      setModelsWithDetails([]);
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchModels();
  }, [fetchModels]);
  
  return {
    isLoading,
    error,
    modelsWithDetails,
    refreshModels: fetchModels,
  };
}

// useModelVaultRegister hook
export function useModelVaultRegister() {
  const { isConnected } = useWallet();
  const [isRegistering, setIsRegistering] = useState(false);
  
  const registerModel = useCallback(async (modelData: {
    modelId?: string;
    fileName: string;
    modelType: ModelType;
    sizeBytes: number;
    displayName?: string;
    description?: string;
    isNSFW?: boolean;
    inpainting?: boolean;
    img2img?: boolean;
    controlnet?: boolean;
    lora?: boolean;
    baseModel?: string;
    architecture?: string;
  }): Promise<{ success: boolean; error?: string }> => {
    if (!isConnected) {
      return { success: false, error: 'Wallet not connected' };
    }
    
    setIsRegistering(true);
    try {
      // TODO: Implement actual blockchain registration
      // For now, return an error to indicate it's not implemented
      return { success: false, error: 'Model registration not yet implemented' };
    } catch (error) {
      return { success: false, error: error instanceof Error ? error.message : 'Unknown error' };
    } finally {
      setIsRegistering(false);
    }
  }, [isConnected]);
  
  return {
    registerModel,
    isRegistering,
    isConnected,
  };
}

// Generate model hash utility
export function generateModelHash(fileName: string): string {
  // Simple hash function for browser compatibility
  // In production, this should match the backend hash generation
  let hash = 0;
  for (let i = 0; i < fileName.length; i++) {
    const char = fileName.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  // Convert to positive hex string
  return Math.abs(hash).toString(16).padStart(16, '0').slice(0, 16);
}

// Re-export ModelType
export { ModelType };


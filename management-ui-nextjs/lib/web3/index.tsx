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

// WalletConnect/Reown Project ID configuration
// 
// To eliminate the 403 error, get a free project ID from https://cloud.walletconnect.com
// Then set it in your .env file: NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=your-project-id
//
// Note: The 403 error is non-critical - RainbowKit gracefully falls back to local config
// The app will work fine without a project ID, but WalletConnect mobile wallet support
// will be disabled (browser extension wallets like MetaMask/Coinbase Wallet still work)
const walletConnectProjectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID;

const config = getDefaultConfig({
  appName: 'AI Power Grid Model Manager',
  // If no project ID is provided, 'default-project-id' triggers a remote config fetch
  // which returns 403. This is handled gracefully - RainbowKit uses local config instead.
  // To fix: Set NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID environment variable
  projectId: walletConnectProjectId || 'default-project-id',
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

// Utility function to normalize sizeBytes to bigint (handles both number and bigint)
export function normalizeSizeBytes(sizeBytes: number | bigint): bigint {
  if (typeof sizeBytes === 'bigint') {
    return sizeBytes;
  }
  return BigInt(Math.floor(sizeBytes));
}

// Model info interface - accepts both number and bigint for compatibility
export interface ModelInfo {
  displayName?: string;
  fileName: string;
  description?: string;
  baseModel?: string;
  modelType: ModelType;
  sizeBytes: number | bigint;
  isNSFW?: boolean;
  inpainting?: boolean;
  img2img?: boolean;
  controlnet?: boolean;
  lora?: boolean;
  architecture?: string;
}

export interface ModelWithDetails {
  hash: string;
  info: ModelInfo | null;
}

// useModelVault hook
export function useModelVault() {
  const { chainId } = useWallet();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [modelsWithDetails, setModelsWithDetails] = useState<ModelWithDetails[]>([]);
  
  const fetchModels = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Use chainId from wallet connection, or default to Base Mainnet (8453)
      // Supported chains: 8453 (Base Mainnet), 84532 (Base Sepolia)
      const targetChainId = chainId || 8453;
      
      // Fetch models from the blockchain via API endpoint with chainId parameter
      const response = await fetch(`/api/blockchain-models?chainId=${targetChainId}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch models: ${response.statusText}`);
      }
      
      const data = await response.json();
      const models = data.models || [];
      
      // Convert API response to ModelWithDetails format
      const modelsWithDetails: ModelWithDetails[] = models.map((model: any) => ({
        hash: model.hash || '',
        info: {
          displayName: model.displayName,
          fileName: model.fileName,
          description: model.description,
          baseModel: model.baseModel,
          modelType: model.modelType,
          sizeBytes: BigInt(model.sizeBytes || 0),
          isNSFW: model.isNSFW,
          // Include additional fields that may be used by the UI
          inpainting: model.inpainting,
          img2img: model.img2img,
          controlnet: model.controlnet,
          lora: model.lora,
          architecture: model.architecture,
        },
      }));
      
      setModelsWithDetails(modelsWithDetails);
    } catch (err) {
      console.error('Error fetching models:', err);
      setError(err instanceof Error ? err : new Error('Failed to fetch models'));
      setModelsWithDetails([]);
    } finally {
      setIsLoading(false);
    }
  }, [chainId]);
  
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

// Type definition for registerModel function parameter
export type RegisterModelParams = {
  modelId?: string;
  fileName: string;
  modelType: ModelType;
  sizeBytes: number | bigint; // Accept both number and bigint for compatibility
  displayName?: string;
  description?: string;
  isNSFW?: boolean;
  inpainting?: boolean;
  img2img?: boolean;
  controlnet?: boolean;
  lora?: boolean;
  baseModel?: string;
  architecture?: string;
};

// Return type for useModelVaultRegister hook
export type UseModelVaultRegisterReturn = {
  registerModel: (modelData: RegisterModelParams) => Promise<{ success: boolean; error?: string }>;
  isRegistering: boolean;
  isConnected: boolean;
};

// useModelVaultRegister hook
export function useModelVaultRegister(): UseModelVaultRegisterReturn {
  const { isConnected } = useWallet();
  const [isRegistering, setIsRegistering] = useState(false);
  
  const registerModel = useCallback(async (modelData: RegisterModelParams): Promise<{ success: boolean; error?: string }> => {
    if (!isConnected) {
      return { success: false, error: 'Wallet not connected' };
    }
    
    setIsRegistering(true);
    try {
      // Normalize sizeBytes to bigint for internal use
      const normalizedSizeBytes = normalizeSizeBytes(modelData.sizeBytes);
      
      // TODO: Implement actual blockchain registration
      // Use normalizedSizeBytes (bigint) for blockchain operations
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

// Re-export ModelType for easier imports
// ModelType is already imported above for internal use, now re-export it
// Note: RegisterModelParams and UseModelVaultRegisterReturn are already exported above as types
export { ModelType };


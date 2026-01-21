import { NextResponse } from 'next/server';
import { createPublicClient, http } from 'viem';
import { base, baseSepolia } from 'viem/chains';
import * as fs from 'fs/promises';

export const dynamic = 'force-dynamic';

// ModelRegistryV2 contract addresses for both networks
const BASE_MAINNET_CONTRACT = process.env.NEXT_PUBLIC_MODELVAULT_CONTRACT_V2_MAINNET || process.env.NEXT_PUBLIC_MODELVAULT_CONTRACT_V2 || '0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609';
const BASE_SEPOLIA_CONTRACT = process.env.NEXT_PUBLIC_MODELVAULT_CONTRACT_V2_SEPOLIA || '0xF5caaB067Bae8ea6Be18903056E20e8DacB92182';

// RPC URLs for both networks
const BASE_MAINNET_RPC = process.env.NEXT_PUBLIC_MODELVAULT_RPC_URL_MAINNET || process.env.NEXT_PUBLIC_MODELVAULT_RPC_URL || 'https://mainnet.base.org';
const BASE_SEPOLIA_RPC = process.env.NEXT_PUBLIC_MODELVAULT_RPC_URL_SEPOLIA || 'https://sepolia.base.org';

// Default network (can be overridden by query parameter)
const DEFAULT_CHAIN_ID = process.env.NEXT_PUBLIC_DEFAULT_CHAIN_ID ? parseInt(process.env.NEXT_PUBLIC_DEFAULT_CHAIN_ID) : 8453; // Base Mainnet

const isWindows = process.platform === 'win32';

// ABI for ModelRegistryV2 contract
// getAllActiveModels() returns only registered active models - ensures blockchain is single source of truth
const MODEL_REGISTRY_V2_ABI = [
  {
    inputs: [],
    name: 'getAllActiveModels',
    outputs: [
      {
        components: [
          { name: 'modelHash', type: 'bytes32' },
          { name: 'modelType', type: 'uint8' },
          { name: 'name', type: 'string' },
          { name: 'description', type: 'string' },
          { name: 'isNSFW', type: 'bool' },
          { name: 'timestamp', type: 'uint256' },
          { name: 'creator', type: 'address' },
          { name: 'inpainting', type: 'bool' },
          { name: 'img2img', type: 'bool' },
          { name: 'controlnet', type: 'bool' },
          { name: 'lora', type: 'bool' },
          { name: 'baseModel', type: 'string' },
          { name: 'architecture', type: 'string' },
          { name: 'isActive', type: 'bool' },
        ],
        internalType: 'struct ModelRegistryV2.Model[]',
        name: '',
        type: 'tuple[]',
      },
    ],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [{ name: 'modelId', type: 'uint256' }],
    name: 'getModelFiles',
    outputs: [
      {
        components: [
          { name: 'fileName', type: 'string' },
          { name: 'fileType', type: 'string' },
          { name: 'downloadUrl', type: 'string' },
          { name: 'mirrorUrl', type: 'string' },
          { name: 'sha256Hash', type: 'bytes32' },
          { name: 'sizeBytes', type: 'uint256' },
        ],
        internalType: 'struct ModelRegistryV2.ModelFile[]',
        name: '',
        type: 'tuple[]',
      },
    ],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [{ name: 'modelHash', type: 'bytes32' }],
    name: 'hashToModelId',
    outputs: [{ type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
] as const;

// Network configuration
const NETWORK_CONFIG = {
  8453: { // Base Mainnet
    chain: base,
    contract: BASE_MAINNET_CONTRACT,
    rpc: BASE_MAINNET_RPC,
    name: 'Base Mainnet',
  },
  84532: { // Base Sepolia
    chain: baseSepolia,
    contract: BASE_SEPOLIA_CONTRACT,
    rpc: BASE_SEPOLIA_RPC,
    name: 'Base Sepolia',
  },
} as const;

function getPublicClient(chainId: number = DEFAULT_CHAIN_ID) {
  const config = NETWORK_CONFIG[chainId as keyof typeof NETWORK_CONFIG];
  if (!config) {
    throw new Error(`Unsupported chain ID: ${chainId}`);
  }
  return createPublicClient({
    chain: config.chain,
    transport: http(config.rpc),
  });
}

function getContractAddress(chainId: number = DEFAULT_CHAIN_ID): string {
  const config = NETWORK_CONFIG[chainId as keyof typeof NETWORK_CONFIG];
  if (!config) {
    throw new Error(`Unsupported chain ID: ${chainId}`);
  }
  return config.contract;
}

// Load descriptions from local catalog to enrich blockchain data
async function loadDescriptionsFromCatalog(): Promise<Record<string, { description: string; sizeBytes: number }>> {
  const data: Record<string, { description: string; sizeBytes: number }> = {};
  
  const catalogPaths = isWindows 
    ? ['c:\\dev\\comfy-bridge\\model_configs.json', 'c:\\dev\\grid-image-model-reference\\stable_diffusion.json']
    : ['/app/comfy-bridge/model_configs.json', '/app/grid-image-model-reference/stable_diffusion.json'];
  
  for (const catalogPath of catalogPaths) {
    try {
      const content = await fs.readFile(catalogPath, 'utf-8');
      const catalog = JSON.parse(content);
      
      for (const [name, modelData] of Object.entries(catalog as Record<string, any>)) {
        const desc = modelData.description || '';
        const sizeMb = modelData.size_mb || 0;
        const sizeBytes = sizeMb * 1024 * 1024;
        
        if (desc || sizeBytes > 0) {
          // Index by multiple keys for flexible matching
          data[name] = { description: desc, sizeBytes };
          data[name.toLowerCase()] = { description: desc, sizeBytes };
          if (modelData.filename) {
            data[modelData.filename] = { description: desc, sizeBytes };
            data[modelData.filename.toLowerCase()] = { description: desc, sizeBytes };
          }
        }
      }
      
      if (Object.keys(data).length > 0) {
        console.log(`[blockchain-models] Loaded ${Object.keys(data).length} entries from catalog: ${catalogPath}`);
        return data;
      }
    } catch {
      // Continue to next path
    }
  }
  
  return data;
}

// Generate description based on model name patterns
function generateDescription(displayName: string): string {
  const nameLower = displayName.toLowerCase();
  
  if (nameLower.includes('wan2.2') || nameLower.includes('wan2_2')) {
    if (nameLower.includes('ti2v') || nameLower.includes('i2v')) {
      return 'WAN 2.2 Image-to-Video generation model';
    } else if (nameLower.includes('t2v')) {
      if (nameLower.includes('hq')) {
        return 'WAN 2.2 Text-to-Video 14B model - High quality mode';
      }
      return 'WAN 2.2 Text-to-Video 14B model';
    }
    return 'WAN 2.2 Video generation model';
  }
  
  if (nameLower.includes('flux')) {
    if (nameLower.includes('flux.2') || nameLower.includes('flux2')) {
      return 'FLUX.2-dev - Next generation text to image model';
    }
    if (nameLower.includes('kontext')) {
      return 'FLUX Kontext model for context-aware image generation';
    }
    if (nameLower.includes('krea')) {
      return 'FLUX Krea model - Advanced image generation';
    }
    return 'FLUX.1 model for high-quality image generation';
  }
  
  if (nameLower.includes('sdxl') || nameLower.includes('xl')) {
    return 'Stable Diffusion XL model';
  }
  
  if (nameLower.includes('chroma')) {
    return 'Chroma model for image generation';
  }
  
  if (nameLower.includes('ltxv')) {
    return 'LTX Video generation model';
  }
  
  return `${displayName} model`;
}

export async function GET(request: Request) {
  // Get chainId from query parameter or use default
  const { searchParams } = new URL(request.url);
  const chainIdParam = searchParams.get('chainId');
  const chainId = chainIdParam ? parseInt(chainIdParam) : DEFAULT_CHAIN_ID;
  
  console.log('[blockchain-models] GET request received');
  console.log('[blockchain-models] Chain ID:', chainId);
  
  const networkConfig = NETWORK_CONFIG[chainId as keyof typeof NETWORK_CONFIG];
  if (!networkConfig) {
    return NextResponse.json({
      success: false,
      models: [],
      error: `Unsupported chain ID: ${chainId}. Supported: 8453 (Base Mainnet), 84532 (Base Sepolia)`,
    }, { status: 400 });
  }
  
  console.log('[blockchain-models] Environment check:', {
    NETWORK: networkConfig.name,
    CONTRACT: networkConfig.contract,
    RPC: networkConfig.rpc,
  });
  
  try {
    const client = getPublicClient(chainId);
    const contractAddress = getContractAddress(chainId) as `0x${string}`;

    console.log(`[blockchain-models] Connecting to ModelRegistryV2 contract ${contractAddress} on ${networkConfig.name} (${networkConfig.rpc})`);

    // Load descriptions from catalog for enrichment
    const catalogData = await loadDescriptionsFromCatalog();

    // Fetch ONLY registered active models from blockchain
    // getAllActiveModels() ensures we only get models that are registered and active
    console.log('[blockchain-models] Calling getAllActiveModels() to fetch registered models...');
    let activeModels: any[];
    try {
      activeModels = await client.readContract({
        address: contractAddress,
        abi: MODEL_REGISTRY_V2_ABI,
        functionName: 'getAllActiveModels',
      }) as any[];
      console.log(`[blockchain-models] Found ${activeModels.length} registered active models on chain`);
    } catch (error: any) {
      console.error('[blockchain-models] Failed to fetch active models:', error.message);
      return NextResponse.json({
        success: false,
        models: [],
        count: 0,
        error: 'Failed to fetch registered models from blockchain: ' + error.message,
      });
    }

    const models: any[] = [];

    // Process each registered model
    for (let i = 0; i < activeModels.length; i++) {
      try {
        const result = activeModels[i];

        // Validate model hash exists
        const modelHash = result.modelHash;
        if (!modelHash || modelHash === '0x0000000000000000000000000000000000000000000000000000000000000000') {
          console.log(`[blockchain-models] Model ${i + 1} has zero hash, skipping`);
          continue;
        }

        // Double-check isActive (should already be filtered by getAllActiveModels, but verify)
        if (result.isActive === false) {
          console.log(`[blockchain-models] Model ${i + 1} is inactive, skipping`);
          continue;
        }

        const displayName = result.name || '';
        
        // Get model files to determine fileName and total size
        let fileName = '';
        let totalSizeBytes = 0;
        try {
          const modelId = await client.readContract({
            address: contractAddress,
            abi: MODEL_REGISTRY_V2_ABI,
            functionName: 'hashToModelId',
            args: [modelHash],
          });
          
          const files = await client.readContract({
            address: contractAddress,
            abi: MODEL_REGISTRY_V2_ABI,
            functionName: 'getModelFiles',
            args: [modelId],
          }) as any[];
          
          if (files && files.length > 0) {
            // Use first file's name as fileName, sum all file sizes
            fileName = files[0].fileName || '';
            totalSizeBytes = files.reduce((sum: number, file: any) => {
              return sum + Number(file.sizeBytes || 0);
            }, 0);
          }
        } catch (fileError: any) {
          console.warn(`[blockchain-models] Could not fetch files for model ${displayName}:`, fileError.message);
        }
        
        // Get description from catalog or generate one
        let description = result.description || '';
        let enrichedSizeBytes = 0;
        
        // Try to find enrichment data from catalog
        const catalogEntry = catalogData[displayName] || 
                            catalogData[displayName.toLowerCase()] ||
                            catalogData[fileName] ||
                            catalogData[fileName.toLowerCase()];
        
        if (catalogEntry) {
          if (!description) description = catalogEntry.description;
          enrichedSizeBytes = catalogEntry.sizeBytes;
        }
        
        // Fall back to generated description if not in catalog
        if (!description) {
          description = generateDescription(displayName);
        }
        
        // Use total file size if available, otherwise use catalog value
        const finalSizeBytes = totalSizeBytes > 0 ? totalSizeBytes : enrichedSizeBytes;

        // Map result to frontend format
        const model = {
          hash: modelHash,
          modelType: Number(result.modelType || 0),
          fileName: fileName || displayName,
          displayName: displayName,
          description: description,
          isNSFW: result.isNSFW || false,
          sizeBytes: finalSizeBytes.toString(),
          inpainting: result.inpainting || false,
          img2img: result.img2img || false,
          controlnet: result.controlnet || false,
          lora: result.lora || false,
          baseModel: result.baseModel || '',
          architecture: result.architecture || '',
          isActive: true, // All models from getAllActiveModels are active
        };

        models.push(model);
        console.log(`[blockchain-models] Registered model ${i + 1}: ${displayName} (${fileName || 'no files'})`);
      } catch (error: any) {
        // Check for rate limiting
        if (error.message?.includes('rate') || error.message?.includes('429')) {
          console.warn(`[blockchain-models] Rate limited at model ${i + 1}, pausing...`);
          await new Promise(r => setTimeout(r, 1000)); // Wait 1 second
          i--; // Retry this model
          continue;
        }
        // Skip models that fail to process
        console.debug(`[blockchain-models] Failed to process model ${i + 1}:`, error.message?.substring(0, 100));
        continue;
      }
    }

    console.log(`[blockchain-models] Successfully fetched ${models.length} registered models from blockchain`);

    // Remove duplicates by displayName (shouldn't happen, but safety check)
    const seenNames = new Set<string>();
    const uniqueModels = models.filter(model => {
      const name = model.displayName.toLowerCase();
      if (seenNames.has(name)) return false;
      seenNames.add(name);
      return true;
    });

    console.log(`[blockchain-models] Returning ${uniqueModels.length} unique registered models`);

    return NextResponse.json({
      success: true,
      models: uniqueModels,
      count: uniqueModels.length,
      total: activeModels.length,
      contractAddress: contractAddress,
      chainId: chainId,
      network: networkConfig.name,
    });
  } catch (error: any) {
    console.error('[blockchain-models] API error:', error);
    return NextResponse.json(
      {
        success: false,
        models: [],
        error: error.message || 'Failed to fetch registered models from blockchain',
      },
      { status: 500 }
    );
  }
}


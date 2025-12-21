import { NextResponse } from 'next/server';
import { createPublicClient, http } from 'viem';
import { base } from 'viem/chains';
import * as fs from 'fs/promises';

export const dynamic = 'force-dynamic';

// Grid ModelVault contract on Base Mainnet - matches Python modelvault_client.py
const MODELVAULT_CONTRACT_ADDRESS = process.env.NEXT_PUBLIC_MODELVAULT_CONTRACT || '0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609';
const MODELVAULT_RPC_URL = process.env.NEXT_PUBLIC_MODELVAULT_RPC_URL || 'https://mainnet.base.org';

const isWindows = process.platform === 'win32';

// ABI matching Grid proxy ModelVault module
// Grid ModelVault struct: modelHash, modelType, fileName, name, version, ipfsCid, downloadUrl,
//                        sizeBytes, quantization, format, vramMB, baseModel, inpainting, img2img,
//                        controlnet, lora, isActive, isNSFW, timestamp, creator
const MODEL_REGISTRY_ABI = [
  {
    inputs: [{ name: 'modelId', type: 'uint256' }],
    name: 'getModel',
    outputs: [
      {
        components: [
          { name: 'modelHash', type: 'bytes32' },
          { name: 'modelType', type: 'uint8' },
          { name: 'fileName', type: 'string' },
          { name: 'name', type: 'string' },
          { name: 'version', type: 'string' },
          { name: 'ipfsCid', type: 'string' },
          { name: 'downloadUrl', type: 'string' },
          { name: 'sizeBytes', type: 'uint256' },
          { name: 'quantization', type: 'string' },
          { name: 'format', type: 'string' },
          { name: 'vramMB', type: 'uint32' },
          { name: 'baseModel', type: 'string' },
          { name: 'inpainting', type: 'bool' },
          { name: 'img2img', type: 'bool' },
          { name: 'controlnet', type: 'bool' },
          { name: 'lora', type: 'bool' },
          { name: 'isActive', type: 'bool' },
          { name: 'isNSFW', type: 'bool' },
          { name: 'timestamp', type: 'uint256' },
          { name: 'creator', type: 'address' },
        ],
        type: 'tuple',
      },
    ],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [],
    name: 'getModelCount',
    outputs: [{ type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
] as const;

function getPublicClient() {
  return createPublicClient({
    chain: base,
    transport: http(MODELVAULT_RPC_URL),
  });
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

export async function GET() {
  console.log('[blockchain-models] GET request received');
  console.log('[blockchain-models] Environment check:', {
    MODELVAULT_CONTRACT: MODELVAULT_CONTRACT_ADDRESS,
    MODELVAULT_RPC: MODELVAULT_RPC_URL,
  });
  
  try {
    const client = getPublicClient();
    const contractAddress = MODELVAULT_CONTRACT_ADDRESS as `0x${string}`;

    console.log(`[blockchain-models] Connecting to contract ${contractAddress} on ${MODELVAULT_RPC_URL}`);

    // Load descriptions from catalog for enrichment
    const catalogData = await loadDescriptionsFromCatalog();

    // Get total model count
    let totalModels: bigint;
    console.log('[blockchain-models] Calling getModelCount()...');
    try {
      totalModels = await client.readContract({
        address: contractAddress,
        abi: MODEL_REGISTRY_ABI,
        functionName: 'getModelCount',
      });
      console.log(`[blockchain-models] Found ${totalModels} models on chain`);
    } catch (error: any) {
      console.error('[blockchain-models] Failed to get model count:', error.message);
      return NextResponse.json({
        success: false,
        models: [],
        count: 0,
        error: 'Failed to get model count from blockchain: ' + error.message,
      });
    }

    const models: any[] = [];
    const total = Number(totalModels);

    console.log(`[blockchain-models] Fetching ${total} models...`);

    // Iterate through all model IDs (1-indexed)
    for (let modelId = 1; modelId <= total; modelId++) {
      try {
        const result = await client.readContract({
          address: contractAddress,
          abi: MODEL_REGISTRY_ABI,
          functionName: 'getModel',
          args: [BigInt(modelId)],
        }) as any;

        // viem returns an object with named properties matching the ABI components
        if (!result || typeof result !== 'object') {
          console.warn(`[blockchain-models] Model ${modelId} returned invalid result type: ${typeof result}`);
          continue;
        }

        // Check if model is valid (modelHash is not zero)
        const modelHash = result.modelHash;
        if (!modelHash || modelHash === '0x0000000000000000000000000000000000000000000000000000000000000000') {
          console.log(`[blockchain-models] Model ${modelId} has zero hash, skipping`);
          continue;
        }

        // Skip inactive models
        if (result.isActive === false) {
          console.log(`[blockchain-models] Model ${modelId} is inactive, skipping`);
          continue;
        }

        const displayName = result.name || '';
        const fileName = result.fileName || '';
        
        // Get description from catalog or generate one
        let description = '';
        let enrichedSizeBytes = 0;
        
        // Try to find enrichment data from catalog
        const catalogEntry = catalogData[displayName] || 
                            catalogData[displayName.toLowerCase()] ||
                            catalogData[fileName] ||
                            catalogData[fileName.toLowerCase()];
        
        if (catalogEntry) {
          description = catalogEntry.description;
          enrichedSizeBytes = catalogEntry.sizeBytes;
        }
        
        // Fall back to generated description if not in catalog
        if (!description) {
          description = generateDescription(displayName);
        }
        
        // Use chain sizeBytes if available, otherwise use catalog value
        const chainSizeBytes = result.sizeBytes ? Number(result.sizeBytes) : 0;
        const finalSizeBytes = chainSizeBytes > 0 ? chainSizeBytes : enrichedSizeBytes;

        // Map result to frontend format
        const model = {
          hash: modelHash,
          modelType: Number(result.modelType || 0),
          fileName: fileName,
          displayName: displayName,
          description: description,
          isNSFW: result.isNSFW || false,
          sizeBytes: finalSizeBytes.toString(),
          inpainting: result.inpainting || false,
          img2img: result.img2img || false,
          controlnet: result.controlnet || false,
          lora: result.lora || false,
          baseModel: result.baseModel || '',
          architecture: result.format || '',
          isActive: result.isActive !== false,
          downloadUrl: result.downloadUrl || '',
          ipfsCid: result.ipfsCid || '',
          quantization: result.quantization || '',
          vramMB: Number(result.vramMB || 0),
        };

        models.push(model);
        console.log(`[blockchain-models] Model ${modelId}: ${displayName} (${fileName})`);
      } catch (error: any) {
        // Check for rate limiting
        if (error.message?.includes('rate') || error.message?.includes('429')) {
          console.warn(`[blockchain-models] Rate limited at model ${modelId}, pausing...`);
          await new Promise(r => setTimeout(r, 1000)); // Wait 1 second
          modelId--; // Retry this model
          continue;
        }
        // Skip models that fail to fetch (might be invalid IDs)
        console.debug(`[blockchain-models] Failed to fetch model ${modelId}:`, error.message?.substring(0, 100));
        continue;
      }
    }

    console.log(`[blockchain-models] Successfully fetched ${models.length} models from blockchain`);

    // Remove duplicates by displayName
    const seenNames = new Set<string>();
    const uniqueModels = models.filter(model => {
      const name = model.displayName.toLowerCase();
      if (seenNames.has(name)) return false;
      seenNames.add(name);
      return true;
    });

    console.log(`[blockchain-models] Returning ${uniqueModels.length} unique models`);

    return NextResponse.json({
      success: true,
      models: uniqueModels,
      count: uniqueModels.length,
      total,
      contractAddress: MODELVAULT_CONTRACT_ADDRESS,
      chainId: 8453, // Base Mainnet
    });
  } catch (error: any) {
    console.error('[blockchain-models] API error:', error);
    return NextResponse.json(
      {
        success: false,
        models: [],
        error: error.message || 'Failed to fetch models from blockchain',
      },
      { status: 500 }
    );
  }
}


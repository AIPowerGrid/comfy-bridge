import { NextResponse } from 'next/server';
import { createPublicClient, http } from 'viem';
import { base } from 'viem/chains';

export const dynamic = 'force-dynamic';

// Grid ModelVault contract on Base Mainnet - matches Python modelvault_client.py
const MODELVAULT_CONTRACT_ADDRESS = process.env.NEXT_PUBLIC_MODELVAULT_CONTRACT || '0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609';
const MODELVAULT_RPC_URL = process.env.NEXT_PUBLIC_MODELVAULT_RPC_URL || 'https://mainnet.base.org';

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

// Model type enum (matches Python ModelType)
enum ModelType {
  TEXT_MODEL = 0,
  IMAGE_MODEL = 1,
  VIDEO_MODEL = 2,
}

function getPublicClient() {
  return createPublicClient({
    chain: base,
    transport: http(MODELVAULT_RPC_URL),
  });
}

export async function GET() {
  try {
    const client = getPublicClient();
    const contractAddress = MODELVAULT_CONTRACT_ADDRESS as `0x${string}`;

    // Get total model count
    let totalModels: bigint;
    try {
      totalModels = await client.readContract({
        address: contractAddress,
        abi: MODEL_REGISTRY_ABI,
        functionName: 'getModelCount',
      });
    } catch (error) {
      console.error('Failed to get model count:', error);
      return NextResponse.json({
        success: true,
        models: [],
        count: 0,
        error: 'Failed to get model count from blockchain',
      });
    }

    const models: any[] = [];
    const total = Number(totalModels);

    console.log(`Fetching ${total} models from blockchain...`);

    // Iterate through all model IDs (1-indexed)
    for (let modelId = 1; modelId <= total; modelId++) {
      try {
        const result = await client.readContract({
          address: contractAddress,
          abi: MODEL_REGISTRY_ABI,
          functionName: 'getModel',
          args: [BigInt(modelId)],
        });

        // Check if model is valid (modelHash is not zero)
        const modelHash = result.modelHash as `0x${string}`;
        if (modelHash === '0x0000000000000000000000000000000000000000000000000000000000000000') {
          continue;
        }

        // Skip inactive models
        if (!result.isActive) {
          continue;
        }

        // Map result to frontend format
        const model = {
          hash: modelHash,
          modelType: Number(result.modelType),
          fileName: result.fileName,
          displayName: result.name,
          description: result.version || '', // version field used as description
          isNSFW: result.isNSFW,
          sizeBytes: result.sizeBytes.toString(), // Convert bigint to string for JSON
          inpainting: result.inpainting,
          img2img: result.img2img,
          controlnet: result.controlnet,
          lora: result.lora,
          baseModel: result.baseModel,
          architecture: result.format,
          isActive: result.isActive,
          downloadUrl: result.downloadUrl,
          ipfsCid: result.ipfsCid,
          quantization: result.quantization,
          vramMB: Number(result.vramMB),
        };

        models.push(model);
      } catch (error) {
        // Skip models that fail to fetch (might be invalid IDs)
        console.debug(`Failed to fetch model ${modelId}:`, error);
        continue;
      }
    }

    console.log(`Successfully fetched ${models.length} models from blockchain`);

    return NextResponse.json({
      success: true,
      models,
      count: models.length,
      total,
      contractAddress: MODELVAULT_CONTRACT_ADDRESS,
    });
  } catch (error: any) {
    console.error('Blockchain models API error:', error);
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

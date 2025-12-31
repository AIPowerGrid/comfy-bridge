/**
 * Register Models to Blockchain
 * 
 * This script registers models from the stable_diffusion.json catalog
 * to the ModelRegistry smart contract on Base Mainnet.
 * 
 * Usage:
 *   node scripts/register-models-to-chain.js [--dry-run] [--model <model-name>]
 * 
 * Environment variables:
 *   PRIVATE_KEY - Private key with registrar role on ModelRegistry
 *   MODELVAULT_CONTRACT - ModelRegistry contract address (optional)
 *   MODELVAULT_RPC_URL - RPC URL (optional, defaults to Base Mainnet)
 * 
 * Options:
 *   --dry-run    Show what would be registered without actually registering
 *   --model      Register only a specific model by name
 *   --list       List all models in catalog
 *   --check      Check which models are already registered
 */

const { ethers } = require('ethers');
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

// Contract configuration
const MODEL_REGISTRY_ADDRESS = process.env.MODELVAULT_CONTRACT || '0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609';
const RPC_URL = process.env.MODELVAULT_RPC_URL || 'https://mainnet.base.org';
// Support multiple env var names for the private key
// Note: WALLET_ID is a wallet address, not a private key, so check PRIVATE_KEY first
const PRIVATE_KEY = process.env.PRIVATE_KEY || process.env.WALLET_PRIVATE_KEY;

// Model type enum matching the contract
const ModelType = {
  TEXT_MODEL: 0,
  IMAGE_MODEL: 1,
  VIDEO_MODEL: 2
};

// ABI for Grid proxy ModelVault module
const MODEL_REGISTRY_ABI = [
  "function getModelCount() view returns (uint256)",
  "function getModel(uint256 modelId) view returns (tuple(bytes32 modelHash, uint8 modelType, string fileName, string name, string version, string ipfsCid, string downloadUrl, uint256 sizeBytes, string quantization, string format, uint32 vramMB, string baseModel, bool inpainting, bool img2img, bool controlnet, bool lora, bool isActive, bool isNSFW, uint256 timestamp, address creator))",
  "function getModelByHash(bytes32 modelHash) view returns (tuple(bytes32 modelHash, uint8 modelType, string fileName, string name, string version, string ipfsCid, string downloadUrl, uint256 sizeBytes, string quantization, string format, uint32 vramMB, string baseModel, bool inpainting, bool img2img, bool controlnet, bool lora, bool isActive, bool isNSFW, uint256 timestamp, address creator))",
  "function isModelExists(uint256 modelId) view returns (bool)",
  "function registerModel(bytes32 modelHash, uint8 modelType, string fileName, string name, string version, string ipfsCid, string downloadUrl, uint256 sizeBytes, string quantization, string format, uint32 vramMB, string baseModel, bool inpainting, bool img2img, bool controlnet, bool lora, bool isNSFW) returns (uint256)",
  "event ModelRegistered(uint256 indexed modelId, bytes32 indexed modelHash, string name, address creator)"
];

/**
 * Calculate model hash from filename (matches contract hashing)
 */
function calculateModelHash(fileName) {
  return ethers.keccak256(ethers.toUtf8Bytes(fileName));
}

/**
 * Load models from stable_diffusion.json catalog
 */
function loadModelsFromCatalog() {
  const catalogPaths = [
    process.env.GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH 
      ? path.join(process.env.GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH, 'stable_diffusion.json')
      : null,
    path.join(__dirname, '..', '..', 'grid-image-model-reference', 'stable_diffusion.json'),
    '/app/grid-image-model-reference/stable_diffusion.json',
  ].filter(Boolean);

  for (const catalogPath of catalogPaths) {
    try {
      if (fs.existsSync(catalogPath)) {
        console.log(`📂 Loading catalog from: ${catalogPath}`);
        const content = fs.readFileSync(catalogPath, 'utf-8');
        return JSON.parse(content);
      }
    } catch (err) {
      console.log(`   Could not load from ${catalogPath}: ${err.message}`);
    }
  }

  throw new Error('Could not find stable_diffusion.json catalog');
}

/**
 * Parse catalog model to contract format
 */
function parseModelForContract(name, data) {
  const config = data.config || {};
  const files = config.files || data.files || [];
  
  // Get primary file info
  const primaryFile = files[0] || {};
  const fileName = primaryFile.path || config.file_name || `${name}.safetensors`;
  
  // Determine model type
  let modelType = ModelType.IMAGE_MODEL;
  const nameLower = name.toLowerCase();
  if (nameLower.includes('video') || nameLower.includes('wan') || nameLower.includes('ltx')) {
    modelType = ModelType.VIDEO_MODEL;
  }
  
  // Calculate size in bytes
  const sizeBytes = BigInt(Math.floor((data.size_mb || data.size_gb * 1024 || 0) * 1024 * 1024));
  
  return {
    modelHash: calculateModelHash(fileName),
    modelType,
    fileName,
    displayName: data.name || name,
    description: data.description || `${name} model for AI image generation`,
    isNSFW: data.nsfw || false,
    sizeBytes,
    inpainting: data.inpainting || nameLower.includes('inpaint'),
    img2img: data.img2img !== false,  // Default true for image models
    controlnet: data.controlnet || false,
    lora: data.type === 'loras' || nameLower.includes('lora'),
    baseModel: data.baseline || data.base_model || '',
    architecture: data.style || data.type || 'checkpoint',
    // Grid ModelVault additional fields
    version: data.version || "1.0",
    ipfsCid: data.ipfs_cid || data.ipfsCid || "",
    downloadUrl: data.download_url || data.downloadUrl || "",
    quantization: data.quantization || "",
    format: data.format || (fileName.endsWith('.safetensors') ? 'safetensors' : fileName.endsWith('.ckpt') ? 'ckpt' : 'safetensors'),
    vramMB: data.vram_mb || data.vramMB || 0
  };
}

/**
 * Get list of already registered models
 */
async function getRegisteredModels(contract) {
  try {
    // Try to call getModelCount - if it fails, the contract might not exist or be wrong type
    let totalModels;
    try {
      totalModels = await contract.getModelCount();
    } catch (err) {
      if (err.code === 'BAD_DATA' || err.message.includes('could not decode') || err.message.includes('function not found')) {
        console.error('⚠️  Contract at this address may not be a Grid ModelVault contract');
        console.error('   Error:', err.message);
        console.error('   This could mean:');
        console.error('   1. Contract not deployed at this address');
        console.error('   2. Wrong contract type/ABI');
        console.error('   3. Contract not initialized');
        console.error('   4. ModelVault module not registered in Grid proxy');
        return [];
      }
      throw err;
    }
    
    console.log(`📊 Total models on-chain: ${totalModels}`);
    
    const models = [];
    for (let i = 1; i <= Number(totalModels); i++) {
      try {
        const model = await contract.getModel(i);
        models.push({
          id: i,
          hash: model[0],
          modelType: Number(model[1]),
          fileName: model[2],
          name: model[3],
          version: model[4]
        });
      } catch (err) {
        console.log(`   ⚠️  Could not fetch model ${i}: ${err.message}`);
      }
    }
    
    return models;
  } catch (err) {
    console.error('Error fetching registered models:', err.message);
    return [];
  }
}

/**
 * Register a single model
 */
async function registerModel(contractWithSigner, modelData, dryRun = false) {
  console.log(`\n📝 Registering: ${modelData.displayName}`);
  console.log(`   File: ${modelData.fileName}`);
  console.log(`   Type: ${['TEXT', 'IMAGE', 'VIDEO'][modelData.modelType]}`);
  console.log(`   Size: ${Number(modelData.sizeBytes) / (1024 * 1024)} MB`);
  console.log(`   Hash: ${modelData.modelHash}`);
  
  if (dryRun) {
    console.log(`   ✅ [DRY RUN] Would register model`);
    return { success: true, dryRun: true };
  }
  
  try {
    // Grid ModelVault registerModel signature:
    // registerModel(bytes32 modelHash, uint8 modelType, string fileName, string name, 
    //               string version, string ipfsCid, string downloadUrl, uint256 sizeBytes,
    //               string quantization, string format, uint32 vramMB, string baseModel,
    //               bool inpainting, bool img2img, bool controlnet, bool lora, bool isNSFW)
    const tx = await contractWithSigner.registerModel(
      modelData.modelHash,
      modelData.modelType,
      modelData.fileName,
      modelData.displayName,
      modelData.version || "1.0",           // version
      modelData.ipfsCid || "",             // ipfsCid
      modelData.downloadUrl || "",          // downloadUrl
      modelData.sizeBytes,
      modelData.quantization || "",         // quantization
      modelData.format || "safetensors",    // format
      modelData.vramMB || 0,                // vramMB
      modelData.baseModel,
      modelData.inpainting,
      modelData.img2img,
      modelData.controlnet,
      modelData.lora,
      modelData.isNSFW
    );
    
    console.log(`   ⏳ Transaction sent: ${tx.hash}`);
    const receipt = await tx.wait();
    console.log(`   ✅ Registered in block ${receipt.blockNumber}`);
    
    return { success: true, txHash: tx.hash, blockNumber: receipt.blockNumber };
  } catch (err) {
    console.error(`   ❌ Failed to register: ${err.message}`);
    return { success: false, error: err.message };
  }
}

/**
 * Main function
 */
async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const listOnly = args.includes('--list');
  const checkOnly = args.includes('--check');
  const specificModel = args.includes('--model') ? args[args.indexOf('--model') + 1] : null;
  
  console.log('🔗 AIPG Model Registry - Register Models to Blockchain');
  console.log('='.repeat(60));
  console.log(`📡 RPC: ${RPC_URL}`);
  console.log(`📜 Contract: ${MODEL_REGISTRY_ADDRESS}`);
  
  if (dryRun) {
    console.log('🏃 DRY RUN MODE - No transactions will be sent');
  }
  
  // Load catalog
  const catalog = loadModelsFromCatalog();
  const modelNames = Object.keys(catalog);
  console.log(`📚 Catalog contains ${modelNames.length} models`);
  
  if (listOnly) {
    console.log('\n📋 Models in catalog:');
    modelNames.forEach((name, i) => {
      const data = catalog[name];
      const type = name.toLowerCase().includes('wan') || name.toLowerCase().includes('ltx') ? 'VIDEO' : 'IMAGE';
      console.log(`   ${i + 1}. ${name} (${type})`);
    });
    return;
  }
  
  // Connect to blockchain
  const provider = new ethers.JsonRpcProvider(RPC_URL);
  const contract = new ethers.Contract(MODEL_REGISTRY_ADDRESS, MODEL_REGISTRY_ABI, provider);
  
  // Get registered models
  const registeredModels = await getRegisteredModels(contract);
  const registeredHashes = new Set(registeredModels.map(m => m.hash.toLowerCase()));
  const registeredNames = new Set(registeredModels.map(m => m.name.toLowerCase()));
  
  console.log(`\n📊 Already registered: ${registeredModels.length} models`);
  
  if (checkOnly) {
    console.log('\n✅ Registered models:');
    registeredModels.forEach((m, i) => {
      console.log(`   ${i + 1}. ${m.name} (${m.fileName})`);
    });
    
    console.log('\n❌ Missing from chain:');
    let missingCount = 0;
    for (const name of modelNames) {
      const modelData = parseModelForContract(name, catalog[name]);
      if (!registeredHashes.has(modelData.modelHash.toLowerCase()) && 
          !registeredNames.has(modelData.displayName.toLowerCase())) {
        console.log(`   - ${modelData.displayName}`);
        missingCount++;
      }
    }
    console.log(`\n📊 Summary: ${registeredModels.length} registered, ${missingCount} missing`);
    return;
  }
  
  // Check for private key (only required for actual registration, not dry-run or check)
  if (!PRIVATE_KEY && !dryRun && !checkOnly) {
    console.error('\n❌ PRIVATE_KEY environment variable required for registration');
    console.log('   Set PRIVATE_KEY (or WALLET_PRIVATE_KEY) in .env file or use --dry-run to preview');
    console.log('   Note: WALLET_ID is a wallet address, not a private key');
    process.exit(1);
  }

  // Create signer if we have a private key (only needed for actual registration)
  let contractWithSigner = null;
  if (PRIVATE_KEY && !dryRun && !checkOnly) {
    try {
      const wallet = new ethers.Wallet(PRIVATE_KEY, provider);
      contractWithSigner = contract.connect(wallet);
      console.log(`\n🔑 Signer: ${wallet.address}`);
      
      const balance = await provider.getBalance(wallet.address);
      console.log(`💰 Balance: ${ethers.formatEther(balance)} ETH`);
    } catch (err) {
      if (err.code === 'INVALID_ARGUMENT' && err.argument === 'privateKey') {
        console.error('\n❌ Invalid private key format');
        console.log('   WALLET_ID is a wallet address, not a private key');
        console.log('   Please set PRIVATE_KEY or WALLET_PRIVATE_KEY with the actual private key');
        process.exit(1);
      }
      throw err;
    }
  }
  
  // Filter models to register
  let modelsToRegister = [];
  
  for (const name of modelNames) {
    if (specificModel && !name.toLowerCase().includes(specificModel.toLowerCase())) {
      continue;
    }
    
    const modelData = parseModelForContract(name, catalog[name]);
    
    // Check if already registered
    if (registeredHashes.has(modelData.modelHash.toLowerCase()) ||
        registeredNames.has(modelData.displayName.toLowerCase())) {
      console.log(`   ⏭️  ${modelData.displayName} - already registered`);
      continue;
    }
    
    modelsToRegister.push(modelData);
  }
  
  console.log(`\n📝 Models to register: ${modelsToRegister.length}`);
  
  if (modelsToRegister.length === 0) {
    console.log('✅ All models already registered!');
    return;
  }
  
  // Register models
  let successCount = 0;
  let failCount = 0;
  
  for (const modelData of modelsToRegister) {
    const result = await registerModel(contractWithSigner || contract, modelData, dryRun);
    if (result.success) {
      successCount++;
    } else {
      failCount++;
    }
    
    // Add delay between transactions to avoid rate limiting
    if (!dryRun && modelsToRegister.indexOf(modelData) < modelsToRegister.length - 1) {
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
  
  console.log('\n' + '='.repeat(60));
  console.log(`📊 Summary: ${successCount} registered, ${failCount} failed`);
}

main().catch(console.error);


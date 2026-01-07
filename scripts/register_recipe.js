#!/usr/bin/env node
/**
 * Register Recipe to RecipeVault via Grid Diamond
 * 
 * IMPORTANT: storeRecipe() requires RECIPE_CREATOR_ROLE
 * Contact admin to get the role granted to your wallet.
 * 
 * Usage:
 *   node scripts/register_recipe.js --workflow ltxv.json --dry-run              # Test without tx
 *   PRIVATE_KEY=0x... node scripts/register_recipe.js --workflow ltxv.json      # Submit tx
 */

require('dotenv').config();
const { ethers } = require('ethers');
const pako = require('pako');
const fs = require('fs');
const path = require('path');

// ============ CONFIGURATION ============

const CONFIG = {
  RPC_URL: process.env.RECIPESVAULT_RPC_URL || process.env.MODELVAULT_RPC_URL || 'https://mainnet.base.org',
  CHAIN_ID: 8453,
  
  // Grid Diamond Contract (all calls go through here)
  GRID_DIAMOND: process.env.RECIPESVAULT_CONTRACT || process.env.MODELVAULT_CONTRACT || '0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609',
  
  // RecipeVault module (upgraded 2026-01-04)
  RECIPE_VAULT_MODULE: '0x58Dc9939FA30C6DE76776eCF24517721D53A9eA0',
};

// Role required to add recipes
const RECIPE_CREATOR_ROLE = ethers.keccak256(ethers.toUtf8Bytes('RECIPE_CREATOR_ROLE'));
const ADMIN_ROLE = ethers.keccak256(ethers.toUtf8Bytes('ADMIN_ROLE'));

const Compression = { None: 0, Gzip: 1, Brotli: 2 };

const RECIPE_VAULT_ABI = [
  // Write
  "function storeRecipe(bytes32 recipeRoot, bytes calldata workflowData, bool canCreateNFTs, bool isPublic, uint8 compression, string calldata name, string calldata description) external returns (uint256 recipeId)",
  "function updateRecipePermissions(uint256 recipeId, bool canCreateNFTs, bool isPublic) external",
  
  // Read
  "function getRecipe(uint256 recipeId) external view returns (tuple(uint256 recipeId, bytes32 recipeRoot, bytes workflowData, address creator, bool canCreateNFTs, bool isPublic, uint8 compression, uint256 createdAt, string name, string description))",
  "function getRecipeByRoot(bytes32 recipeRoot) external view returns (tuple(uint256 recipeId, bytes32 recipeRoot, bytes workflowData, address creator, bool canCreateNFTs, bool isPublic, uint8 compression, uint256 createdAt, string name, string description))",
  "function getCreatorRecipes(address creator) external view returns (uint256[])",
  "function getTotalRecipes() external view returns (uint256)",
  "function getMaxWorkflowBytes() external view returns (uint256)",
  "function hasRole(bytes32 role, address account) external view returns (bool)",
  
  // Events
  "event RecipeStored(uint256 indexed recipeId, bytes32 indexed recipeRoot, address creator)",
];

// ============ HELPERS ============

function loadWorkflow(workflowPath) {
  const workflowFile = path.resolve(workflowPath);
  
  // Try multiple locations if relative path
  const possiblePaths = [
    workflowFile,
    path.join(__dirname, '..', 'workflows', path.basename(workflowPath)),
    path.join(__dirname, '..', path.basename(workflowPath)),
  ];
  
  for (const p of possiblePaths) {
    if (fs.existsSync(p)) {
      return JSON.parse(fs.readFileSync(p, 'utf8'));
    }
  }
  
  throw new Error(`Workflow file not found: ${workflowPath}`);
}

function compressWorkflow(workflowJson) {
  const jsonString = JSON.stringify(workflowJson);
  const compressed = pako.gzip(jsonString);
  return {
    bytes: ethers.hexlify(compressed),
    originalSize: jsonString.length,
    compressedSize: compressed.length,
    ratio: ((1 - compressed.length / jsonString.length) * 100).toFixed(1)
  };
}

function calculateRecipeRoot(workflowJson) {
  return ethers.keccak256(ethers.toUtf8Bytes(JSON.stringify(workflowJson)));
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

// ============ MAIN ============

async function main() {
  const args = process.argv.slice(2);
  const DRY_RUN = args.includes('--dry-run');
  const workflowIndex = args.indexOf('--workflow');
  const workflowPath = workflowIndex >= 0 && args[workflowIndex + 1] ? args[workflowIndex + 1] : 'ltxv.json';
  const nameIndex = args.indexOf('--name');
  const recipeName = nameIndex >= 0 && args[nameIndex + 1] ? args[nameIndex + 1] : null;
  const descIndex = args.indexOf('--description');
  const recipeDescription = descIndex >= 0 && args[descIndex + 1] ? args[descIndex + 1] : '';
  
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║       AIPG RecipeVault - Register Recipe                 ║');
  if (DRY_RUN) console.log('║                    🧪 DRY RUN MODE                          ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  const privateKey = process.env.PRIVATE_KEY || process.env.WALLET_PRIVATE_KEY;
  if (!privateKey && !DRY_RUN) {
    console.error('❌ PRIVATE_KEY required');
    console.log('\nUsage:');
    console.log('  node scripts/register_recipe.js --workflow ltxv.json --dry-run');
    console.log('  PRIVATE_KEY=0x... node scripts/register_recipe.js --workflow ltxv.json');
    process.exit(1);
  }

  // Connect
  console.log('📡 Connecting to Base Mainnet...');
  const provider = new ethers.JsonRpcProvider(CONFIG.RPC_URL);
  const network = await provider.getNetwork();
  console.log(`   Chain ID: ${network.chainId}`);
  
  let signer = null;
  let signerAddress = null;
  
  if (!DRY_RUN && privateKey) {
    signer = new ethers.Wallet(privateKey, provider);
    signerAddress = signer.address;
    console.log(`   Signer: ${signerAddress}`);
    
    const balance = await provider.getBalance(signerAddress);
    console.log(`   Balance: ${ethers.formatEther(balance)} ETH`);
    
    if (balance === 0n) {
      console.error('❌ Wallet has no ETH for gas');
      process.exit(1);
    }
  }

  const contract = new ethers.Contract(CONFIG.GRID_DIAMOND, RECIPE_VAULT_ABI, signer || provider);

  // Check role (if not dry run)
  if (!DRY_RUN && signerAddress) {
    console.log('\n🔐 Checking permissions...');
    const hasCreatorRole = await contract.hasRole(RECIPE_CREATOR_ROLE, signerAddress);
    const hasAdminRole = await contract.hasRole(ADMIN_ROLE, signerAddress);
    
    if (hasCreatorRole) {
      console.log('   ✅ Has RECIPE_CREATOR_ROLE');
    } else if (hasAdminRole) {
      console.log('   ✅ Has ADMIN_ROLE (can create recipes)');
    } else {
      console.error('   ❌ Missing RECIPE_CREATOR_ROLE');
      console.log('\n   Your wallet does not have permission to add recipes.');
      console.log('   Contact the admin to grant RECIPE_CREATOR_ROLE to:');
      console.log(`   ${signerAddress}`);
      console.log('\n   Authorized wallets:');
      console.log('   - 0xA218db26ed545f3476e6c3E827b595cf2E182533 (admin)');
      console.log('   - 0xe2dddddf4dd22e98265bbf0e6bdc1cb3a4bb26a8');
      process.exit(1);
    }
  }

  // Check state
  console.log('\n📊 RecipeVault State:');
  const totalRecipes = await contract.getTotalRecipes();
  const maxBytes = await contract.getMaxWorkflowBytes();
  console.log(`   Total Recipes: ${totalRecipes}`);
  console.log(`   Max Size: ${formatBytes(Number(maxBytes))}`);

  // Load workflow
  console.log('\n📂 Loading Workflow...');
  let workflow;
  try {
    workflow = loadWorkflow(workflowPath);
    console.log(`   ✓ Loaded: ${workflowPath}`);
    console.log(`   Nodes: ${Object.keys(workflow).length}`);
  } catch (e) {
    console.error(`❌ Failed to load workflow: ${e.message}`);
    process.exit(1);
  }

  // Compress
  console.log('\n🗜️  Compressing...');
  const compressed = compressWorkflow(workflow);
  console.log(`   ${formatBytes(compressed.originalSize)} → ${formatBytes(compressed.compressedSize)} (${compressed.ratio}% reduction)`);

  if (maxBytes > 0n && BigInt(compressed.compressedSize) > maxBytes) {
    console.error(`❌ Workflow too large! Max: ${formatBytes(Number(maxBytes))}`);
    process.exit(1);
  }

  // Recipe root
  const recipeRoot = calculateRecipeRoot(workflow);
  console.log(`\n🔑 Recipe Root: ${recipeRoot.slice(0, 22)}...`);

  // Check exists
  console.log('\n🔍 Checking if exists...');
  try {
    const existing = await contract.getRecipeByRoot(recipeRoot);
    if (existing.recipeId > 0n) {
      console.log(`   ⚠️  Already exists: Recipe #${existing.recipeId}`);
      console.log(`   Name: ${existing.name}`);
      console.log(`   Creator: ${existing.creator}`);
      return;
    }
  } catch (e) {}
  console.log('   ✓ Recipe is new');

  // Recipe details
  const finalRecipeName = recipeName || path.basename(workflowPath, '.json').replace(/[-_]/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  const finalDescription = recipeDescription || `${finalRecipeName} workflow for AI generation`;

  console.log('\n📝 Recipe:');
  console.log(`   Name: ${finalRecipeName}`);
  console.log(`   Description: ${finalDescription.substring(0, 50)}...`);
  console.log(`   Can Create NFTs: true`);
  console.log(`   Is Public: true`);

  if (DRY_RUN) {
    console.log('\n════════════════════════════════════════════════════════════════');
    console.log('   🧪 DRY RUN COMPLETE');
    console.log('');
    console.log('   To submit, run with PRIVATE_KEY:');
    console.log('   PRIVATE_KEY=0x... node scripts/register_recipe.js --workflow ltxv.json');
    console.log('');
    console.log('   NOTE: Your wallet needs RECIPE_CREATOR_ROLE');
    console.log('════════════════════════════════════════════════════════════════\n');
    return;
  }

  // Submit
  console.log('\n📤 Submitting...');
  try {
    const tx = await contract.storeRecipe(
      recipeRoot, compressed.bytes, true, true,
      Compression.Gzip, finalRecipeName, finalDescription
    );
    
    console.log(`   Tx: ${tx.hash}`);
    console.log('   ⏳ Confirming...');
    
    const receipt = await tx.wait();
    console.log(`   ✅ Block ${receipt.blockNumber} | Gas: ${receipt.gasUsed}`);

    const event = receipt.logs.find(log => {
      try { return contract.interface.parseLog(log)?.name === 'RecipeStored'; }
      catch { return false; }
    });

    if (event) {
      const parsed = contract.interface.parseLog(event);
      console.log(`\n🎉 Recipe Stored!`);
      console.log(`   ID: ${parsed.args[0]}`);
      console.log(`   Creator: ${parsed.args[2]}`);
    }
    
  } catch (error) {
    console.error('\n❌ Failed:', error.message);
    
    if (error.message.includes('not recipe creator')) {
      console.log('\n   Your wallet lacks RECIPE_CREATOR_ROLE.');
      console.log('   Contact admin to get access.');
    }
    process.exit(1);
  }

  console.log('\n════════════════════════════════════════════════════════════════');
  console.log('   Recipe added successfully!');
  console.log('════════════════════════════════════════════════════════════════\n');
}

main().catch(console.error);


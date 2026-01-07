# How to Register LTXV Recipe Using JavaScript Script

## Quick Start

The JavaScript script works, so use it instead of Python. Here's how:

### Step 1: Install Dependencies

```bash
cd comfy-bridge
npm install
```

This will install:
- `ethers` - Ethereum library
- `pako` - Gzip compression
- `dotenv` - Environment variable loader

### Step 2: Set Your Private Key

**Option A: Create `.env` file** (recommended)
```bash
# Create .env file in comfy-bridge directory
echo "PRIVATE_KEY=0x_your_private_key_here" > .env
```

**Option B: Set environment variable directly**
```bash
# Windows PowerShell
$env:PRIVATE_KEY="0x_your_private_key_here"

# Windows CMD
set PRIVATE_KEY=0x_your_private_key_here

# Linux/Mac/Git Bash
export PRIVATE_KEY=0x_your_private_key_here
```

### Step 3: Run the Script

**Dry run first (test without submitting):**
```bash
node scripts/register_recipe.js --workflow ltxv.json --dry-run
```

**Actually register:**
```bash
node scripts/register_recipe.js --workflow ltxv.json
```

**With custom name/description:**
```bash
node scripts/register_recipe.js --workflow ltxv.json --name "LTXV" --description "LTX-Video workflow for generating videos"
```

## Important: Role Requirement

**Your wallet MUST have `RECIPE_CREATOR_ROLE`** to register recipes.

The script will automatically check this and tell you if you're missing the role.

If you get a role error:
- Your wallet: `0xe2dddDDf4dD22e98265BBf0E6bDC1cB3A4Bb26a8`
- Contact admin to grant `RECIPE_CREATOR_ROLE`
- Admin address: `0xA218db26ed545f3476e6c3E827b595cf2E182533`

## Example Output

```
╔════════════════════════════════════════════════════════════╗
║       AIPG RecipeVault - Register Recipe                 ║
╚════════════════════════════════════════════════════════════╝

📡 Connecting to Base Mainnet...
   Chain ID: 8453
   Signer: 0xe2dddDDf4dD22e98265BBf0E6bDC1cB3A4Bb26a8
   Balance: 0.00197 ETH

🔐 Checking permissions...
   ✅ Has RECIPE_CREATOR_ROLE

📊 RecipeVault State:
   Total Recipes: 0
   Max Size: 100.00 KB

📂 Loading Workflow...
   ✓ Loaded: workflows/ltxv.json
   Nodes: 12

🗜️  Compressing...
   2.40 KB → 0.93 KB (61.3% reduction)

🔑 Recipe Root: 0x6e72365ab8f7b33c7e59ad...

🔍 Checking if exists...
   ✓ Recipe is new

📝 Recipe:
   Name: Ltxv
   Description: LTX-Video workflow for generating videos
   Can Create NFTs: true
   Is Public: true

📤 Submitting...
   Tx: 0x...
   ⏳ Confirming...
   ✅ Block 40373563 | Gas: 492898

🎉 Recipe Stored!
   ID: 1
   Creator: 0xe2dddDDf4dD22e98265BBf0E6bDC1cB3A4Bb26a8
```

## Troubleshooting

### "Cannot find module 'ethers'"
```bash
npm install ethers pako dotenv
```

### "PRIVATE_KEY required"
- Make sure `.env` file exists with `PRIVATE_KEY=0x...`
- Or set environment variable before running

### "Missing RECIPE_CREATOR_ROLE"
- Contact admin to grant role to your wallet
- Script will show your wallet address

### "Wallet has no ETH for gas"
- You need ETH on Base Mainnet
- Get some from a faucet or exchange

### "Workflow file not found"
- Make sure `workflows/ltxv.json` exists
- Or provide full path: `--workflow /full/path/to/ltxv.json`

## After Registration

Once registered successfully:
1. ✅ Recipe is stored on-chain
2. ✅ Bridge can sync it (set `RECIPESVAULT_USE_LOCAL_SDK=false`)
3. ✅ API will recognize "ltxv" as a valid model
4. ✅ Jobs for "ltxv" will be accepted

## Verify Registration

Check if recipe was registered:
```bash
# Using Python check script
python scripts/check_recipe_registration.py --workflow ltxv.json
```

Or check on BaseScan:
- Transaction hash will be shown in the output
- Visit: https://basescan.org/tx/<tx-hash>

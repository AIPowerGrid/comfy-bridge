# LTXV Model Registration Issue and Solution

## Problem

The `ltxv` model/workflow was not being recognized by the API, resulting in the error:
```
"Unfortunately we cannot accept workers serving unrecognised models at this time"
```

## Root Cause

The API validates model names against what's registered on-chain. There are two types of on-chain registration:

1. **Model Registration** (ModelVault) - Registers actual model files (e.g., `ltx-video-2b-v0.9.safetensors`)
2. **Recipe Registration** (RecipeVault) - Registers workflows/recipes (e.g., `ltxv.json`)

The `ltxv` workflow file exists locally (`workflows/ltxv.json`), but it was **not registered as a recipe** in RecipeVault on-chain. The API only accepts models/recipes that are registered on-chain.

## Solution

Register the `ltxv.json` workflow as a recipe in RecipeVault using the provided script.

### Step 1: Register the Recipe

Run the registration script:

```bash
# Dry run first to see what will be registered
python scripts/register_recipe_to_chain.py --workflow ltxv.json --dry-run

# Actually register (requires PRIVATE_KEY with admin role)
python scripts/register_recipe_to_chain.py --workflow ltxv.json \
    --name "ltxv" \
    --description "LTX-Video workflow for generating 30 FPS videos at 1216×704"
```

### Environment Variables Required

Set in your `.env` file:
- `PRIVATE_KEY` - Private key with admin role on RecipeVault
- `RECIPESVAULT_CONTRACT` - Contract address (defaults to ModelVault address: `0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609`)
- `RECIPESVAULT_RPC_URL` - RPC URL (defaults to `https://mainnet.base.org`)

### Step 2: Verify Registration

After registration, the bridge should be able to advertise `ltxv` and the API will accept it.

## Additional Fix

Fixed a syntax error in `comfy_bridge/recipevault_client.py` (line 236) that was causing:
```
expected an indented block after 'if' statement on line 236
```

## Script Usage

```bash
# Register ltxv workflow
python scripts/register_recipe_to_chain.py --workflow ltxv.json

# Register with custom name and description
python scripts/register_recipe_to_chain.py \
    --workflow ltxv.json \
    --name "LTX-Video" \
    --description "LTX-Video workflow for video generation"

# Dry run (preview without registering)
python scripts/register_recipe_to_chain.py --workflow ltxv.json --dry-run
```

## Notes

- The script automatically compresses the workflow using gzip before storing on-chain
- The recipe root hash is calculated from the normalized JSON (keccak256)
- The script checks if the recipe already exists before registering
- Recipes must be registered by an account with admin role on RecipeVault


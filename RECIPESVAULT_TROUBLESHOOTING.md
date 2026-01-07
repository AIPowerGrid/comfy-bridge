# RecipeVault Troubleshooting Guide

## Issue: Recipe Registered but Not Showing Up

### Problem

After successfully registering a recipe (like `ltxv.json`), the bridge shows:
```
Loaded 0 recipes from aipg-smart-contracts
Recipe sync completed: 0 synced, 0 failed
```

Even though the registration transaction succeeded.

### Root Causes

1. **Local SDK Mode Enabled**: `RECIPESVAULT_USE_LOCAL_SDK` defaults to `"true"`, which makes the client read from local files instead of querying the blockchain.

2. **RecipeVault Facet Not Available**: The RecipeVault facet may not be registered in the Grid diamond proxy, causing blockchain queries to fail.

### Solutions

#### Solution 1: Disable Local SDK Mode

Set the environment variable to query the blockchain:

```bash
# In your .env file or environment
RECIPESVAULT_USE_LOCAL_SDK=false
```

This will make the RecipeVault client query the blockchain instead of reading local files.

#### Solution 2: Verify Recipe Registration

Use the check script to verify the recipe is actually on-chain:

```bash
# Check if recipe exists by root hash
python scripts/check_recipe_registration.py --recipe-root 0x6e72365ab8f7b33c7e59adf9490cf5ef1486702a082e5ba80d0dfbf1126ff2ee

# Or calculate root from workflow file
python scripts/check_recipe_registration.py --workflow ltxv.json
```

This will:
- Check if RecipeVault facet is available
- Show total recipes on-chain
- Verify if your specific recipe exists

#### Solution 3: Check RecipeVault Facet Status

The RecipeVault must be registered as a facet in the Grid diamond proxy. If `getTotalRecipes()` returns 0 or fails, the facet may not be registered.

Check the logs for:
```
RecipeVault facet not registered in diamond proxy
```

If you see this, the RecipeVault facet needs to be added to the diamond proxy contract.

### Environment Variables

Key environment variables for RecipeVault:

```bash
# Disable local SDK mode to query blockchain
RECIPESVAULT_USE_LOCAL_SDK=false

# Contract address (same as ModelVault - diamond proxy)
RECIPESVAULT_CONTRACT=0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609

# RPC URL
RECIPESVAULT_RPC_URL=https://mainnet.base.org
```

### How It Works

1. **Local SDK Mode** (`RECIPESVAULT_USE_LOCAL_SDK=true`):
   - Reads recipes from JSON files in `aipg-smart-contracts` directory
   - Does NOT query blockchain
   - Used for development/testing

2. **Blockchain Mode** (`RECIPESVAULT_USE_LOCAL_SDK=false`):
   - Queries RecipeVault facet through diamond proxy
   - Requires RecipeVault facet to be registered
   - Syncs recipes to local files every 12 hours

### Verification Steps

1. **Check if recipe was registered**:
   ```bash
   python scripts/check_recipe_registration.py --workflow ltxv.json
   ```

2. **Check RecipeVault facet availability**:
   The check script will tell you if the facet is available.

3. **Check bridge logs**:
   Look for:
   - `RecipeVault using local SDK mode` - means local mode is active
   - `RecipeVault facet is available` - means blockchain mode is working
   - `RecipeVault facet not registered` - means facet needs to be added

### Expected Behavior After Fix

After setting `RECIPESVAULT_USE_LOCAL_SDK=false` and restarting the bridge:

```
[INFO] RecipeVault using diamond proxy contract: 0x79F39f2a...
[INFO] RecipeVault facet is available in the diamond proxy
[INFO] Fetching 1 recipes from blockchain...
[INFO] Loaded 1 active recipes from blockchain
[INFO] Recipe sync completed: 1 synced, 0 failed
```

### Notes

- Recipes registered on-chain will be synced to `workflows/` directory automatically
- The sync happens every 12 hours, or immediately on startup
- Local workflow files take precedence over synced recipes
- If RecipeVault facet is not available, the bridge falls back to local workflow files


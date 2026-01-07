# Fix: Bridge Not Loading Recipes from Blockchain

## Problem

The bridge is loading **0 recipes** even though there are **2 recipes** confirmed on-chain.

## Root Cause

The bridge is using **local SDK mode** (`RECIPESVAULT_USE_LOCAL_SDK=true`), which makes it read from local files in `/app/aipg-smart-contracts` instead of querying the blockchain.

Since the recipes are registered on-chain but not in the local files, the bridge finds 0 recipes.

## Solution

**Disable local SDK mode** to read from the blockchain:

### Option 1: Set Environment Variable in Docker

If running with Docker Compose, add to your `.env` file or `docker-compose.yml`:

```bash
RECIPESVAULT_USE_LOCAL_SDK=false
```

### Option 2: Set Environment Variable Directly

```bash
export RECIPESVAULT_USE_LOCAL_SDK=false
```

### Option 3: Update docker-compose.yml

Add to the `environment` section:

```yaml
services:
  comfy-bridge:
    environment:
      - RECIPESVAULT_USE_LOCAL_SDK=false
```

## After Changing

1. **Restart the bridge**:
   ```bash
   docker-compose restart comfy-bridge
   ```

2. **Check logs** - you should see:
   ```
   RecipeVault using diamond proxy contract: 0x79F39f2a...
   Loaded 2 recipes from blockchain
   ```

3. **Verify recipes are loaded**:
   - Check logs for "Loaded X recipes"
   - Recipes should sync automatically every 12 hours
   - Or trigger manual sync via API

## Verification

After restarting, check the logs. You should see:
- `RecipeVault using diamond proxy contract` (not "local SDK mode")
- `Loaded 2 recipes from blockchain` (or however many are registered)
- `Recipe sync completed: 2 synced, 0 failed`

## Why This Happens

- **Local SDK mode** (`RECIPESVAULT_USE_LOCAL_SDK=true`) is the default for development
- It reads from local JSON files in `aipg-smart-contracts` directory
- **Blockchain mode** (`RECIPESVAULT_USE_LOCAL_SDK=false`) queries the RecipeVault contract on-chain
- Since recipes are registered on-chain but not in local files, local mode finds 0 recipes

## Notes

- Local SDK mode is useful for development/testing without blockchain access
- For production with on-chain recipes, use blockchain mode (`false`)
- The bridge will automatically sync recipes from blockchain to local files for caching
- Recipes sync every 12 hours automatically, or can be triggered manually


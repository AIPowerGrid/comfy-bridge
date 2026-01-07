# Recipe Registration Summary - LTXV Model

## Current Status

❌ **Recipe registration is failing** - Transaction reverts every time  
✅ **Local workflow file exists** - `workflows/ltxv.json` is available  
⚠️ **API rejects "ltxv"** - Not recognized because not registered on-chain

## Problem

The `storeRecipe` function in RecipeVault is **not registered** in the Grid diamond proxy. This is a Grid infrastructure issue.

### Evidence

- ✅ `getTotalRecipes()` works (read function registered)
- ❌ `storeRecipe()` fails (write function NOT registered)
- ✅ Function signature is correct (simulation succeeds)
- ❌ Transaction reverts (diamond proxy can't route the call)

### Failed Transactions

1. `0x7021fe4713e1c4aa6f1ed019cf2a23d1eb61c7af319861348359ddd5b51222b5` - Block 40373274
2. `0xe25c2951a01077af1b1e8a37cb62f142d1bcedd3ccb056d02640bee3ef639616` - Block 40373539
3. `0x5b828b5c5326b1a03ecda17b12a10bf74172ce3d1fa3f7ed0f57cdbff3a6001f` - Block 40373563

All transactions revert with the same issue.

## What Works

### Local Workflow Usage

The bridge CAN use the local workflow file:

```bash
# Workflow file exists
workflows/ltxv.json

# Bridge configuration
RECIPESVAULT_USE_LOCAL_SDK=true  # Default
WORKFLOW_FILE=ltxv.json
```

The bridge will:
- ✅ Load `ltxv.json` from local files
- ✅ Use it to process jobs
- ✅ Generate images/videos

### What Doesn't Work

**API Recognition**: The API rejects "ltxv" jobs because:
- API validates model names against on-chain registrations
- "ltxv" is not registered on-chain
- API returns: `"Unfortunately we cannot accept workers serving unrecognised models at this time"`

## Solutions

### Option 1: Fix RecipeVault Registration (Grid Team)

**Required Action**: Contact Grid team to:
1. Register RecipeVault facet fully in Grid diamond proxy
2. Register all function selectors (including `storeRecipe`)
3. Verify write functions work

**After Fix**:
```bash
python scripts/register_recipe_to_chain.py --workflow ltxv.json
```

### Option 2: Use Alternative Registration Method

If RecipeVault has an admin-only registration function, you may need:
- Admin role on Grid contract
- Or contact Grid team to register on your behalf

### Option 3: API Configuration Change

Request API team to:
- Accept local/fallback model names
- Or whitelist "ltxv" as a recognized model
- Or allow workers to serve unregistered models (with warning)

### Option 4: Register as Model Instead of Recipe

Check if "ltxv" can be registered in ModelVault instead:
- ModelVault appears to be working (models are registered)
- May need to register the model file, not the workflow

## Current Workaround

**Use local workflows** (already working):
- Bridge uses `workflows/ltxv.json` locally
- Jobs can be processed locally
- But API won't send jobs until model is recognized

**For API recognition**, you need on-chain registration, which requires RecipeVault to be fixed first.

## Next Steps

1. ✅ **Documented the issue** - This file
2. ⏳ **Contact Grid team** - Report RecipeVault registration issue
3. ⏳ **Wait for fix** - RecipeVault write functions need to be registered
4. ⏳ **Register recipe** - After fix, register ltxv.json
5. ⏳ **Verify API** - Confirm API accepts "ltxv" jobs

## Files Created

- `scripts/register_recipe_to_chain.py` - Registration script
- `scripts/check_recipe_registration.py` - Verification script
- `scripts/debug_recipe_registration.py` - Debug script
- `scripts/check_transaction.py` - Transaction checker
- `RECIPE_REGISTRATION_SUMMARY.md` - This file
- `RECIPESVAULT_NOT_REGISTERED.md` - Technical details
- `RECIPE_REGISTRATION_FAILED.md` - Troubleshooting guide

## Contact Information

For Grid infrastructure issues:
- Grid Contract: `0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609`
- BaseScan: https://basescan.org/address/0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609
- Issue: RecipeVault `storeRecipe` function not registered in diamond proxy


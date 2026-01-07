# Recipe Registration Failed - Troubleshooting

## Issue

The recipe registration transaction succeeded (got a transaction hash) but the transaction itself **failed** (status: FAILED).

Transaction: `0x7021fe4713e1c4aa6f1ed019cf2a23d1eb61c7af319861348359ddd5b51222b5`

## Root Cause

The transaction was **reverted** by the smart contract. This means:
- The transaction was sent successfully
- But the contract rejected it during execution
- No state changes occurred
- The recipe was NOT stored

## Why This Happened

The simulation of `storeRecipe` succeeds, but the actual transaction fails. This suggests:

1. **Diamond Proxy Routing Issue**: The RecipeVault facet may not be properly registered in the Grid diamond proxy, causing the call to fail when actually executed (even though simulation works).

2. **Function Not Found**: The diamond proxy may not be routing `storeRecipe` calls to the RecipeVault facet correctly.

3. **Access Control**: There may be access control checks that only apply during actual execution, not simulation.

## Evidence

- `getTotalRecipes()` returns 0 (no recipes stored)
- `getRecipeByRoot()` returns recipe ID 0 (recipe doesn't exist)
- Transaction status: FAILED
- Simulation succeeds (function signature is correct)

## Solutions

### Option 1: Verify RecipeVault Facet Registration

The RecipeVault facet needs to be registered in the Grid diamond proxy. Check if:
- The facet is deployed
- The facet is registered in the diamond proxy
- The function selectors are properly routed

### Option 2: Use Admin Function Instead

If `storeRecipe` requires admin access, you may need to use a different function or ensure your address has the admin role.

### Option 3: Contact Grid Team

Since RecipeVault is part of the Grid infrastructure, you may need to:
- Contact the Grid team to register recipes
- Have them verify the RecipeVault facet is properly set up
- Get admin access if required

## Next Steps

1. **Check Transaction on BaseScan**: 
   - Visit: https://basescan.org/tx/0x7021fe4713e1c4aa6f1ed019cf2a23d1eb61c7af319861348359ddd5b51222b5
   - Look for revert reason in the transaction details

2. **Verify RecipeVault Setup**:
   - Check if RecipeVault facet is registered in diamond proxy
   - Verify function selectors are routed correctly

3. **Alternative Approach**:
   - Use local workflow files until RecipeVault is properly configured
   - Set `RECIPESVAULT_USE_LOCAL_SDK=true` and place workflow files in the expected location

## Current Workaround

Until RecipeVault is properly configured, you can:

1. **Use Local Workflows**: Place `ltxv.json` in the `workflows/` directory
2. **Set Environment Variable**: `RECIPESVAULT_USE_LOCAL_SDK=true`
3. **The bridge will use local workflow files** instead of querying the blockchain

The workflow file already exists at `workflows/ltxv.json`, so the bridge should be able to use it locally even without blockchain registration.


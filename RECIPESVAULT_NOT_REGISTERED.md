# RecipeVault Not Fully Registered in Grid Diamond Proxy

## Issue

The `storeRecipe` function is failing because the RecipeVault facet is **not fully registered** in the Grid diamond proxy.

## Evidence

1. ✅ **Read functions work**: `getTotalRecipes()` succeeds
2. ❌ **Write functions fail**: `storeRecipe()` reverts
3. ✅ **Simulation succeeds**: Function signature is correct
4. ❌ **Transaction fails**: Diamond proxy can't route the call

## Root Cause

The Grid diamond proxy uses function selectors to route calls to modules. When you call `storeRecipe()`, the proxy looks up the function selector in its module mapping:

```solidity
address module = address(bytes20(gs.modules[msg.sig]));
require(module != address(0), "Grid: function not found");
```

If the function selector for `storeRecipe` is not registered, the proxy reverts with "Grid: function not found".

## Why Read Functions Work But Write Functions Don't

This suggests:
- Some RecipeVault functions (read functions) ARE registered
- But write functions like `storeRecipe` are NOT registered
- This is a partial registration issue

## Solution

**This is a Grid infrastructure issue that needs to be fixed by the Grid team:**

1. **Register RecipeVault Facet**: The RecipeVault module needs to be fully registered in the Grid diamond proxy
2. **Register Function Selectors**: All RecipeVault function selectors (including `storeRecipe`) need to be added to the module mapping
3. **Verify Registration**: After registration, both read and write functions should work

## Workaround: Use Local Workflows

Until RecipeVault is properly registered, use local workflow files:

1. **Keep workflow file**: `workflows/ltxv.json` already exists
2. **Set environment variable**: `RECIPESVAULT_USE_LOCAL_SDK=true` (default)
3. **Bridge will use local files**: The bridge will read from `workflows/` directory

## API Recognition Issue

**Important**: Even with local workflows, the API may still reject "ltxv" jobs because:
- The API validates model names against on-chain registrations
- If "ltxv" is not registered on-chain, the API won't accept it

**To fix API recognition**, you need:
1. RecipeVault properly registered (Grid team)
2. Recipe registered on-chain (after RecipeVault is fixed)
3. OR: API needs to accept local/fallback model names

## Next Steps

1. **Contact Grid Team**: Report that RecipeVault write functions are not registered
2. **Request Registration**: Ask them to register all RecipeVault function selectors
3. **Verify After Fix**: Once fixed, try registration again
4. **Use Local Workflows**: In the meantime, use local workflow files

## Checking Registration Status

You can verify if RecipeVault is registered by checking:
- BaseScan: https://basescan.org/address/0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609#readContract
- Look for "modules" mapping or function selector registration
- Try calling `storeRecipe` - if it reverts with "Grid: function not found", it's not registered


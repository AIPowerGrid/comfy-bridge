# Migration Guide: JSON Catalog → Blockchain Registry

## Overview

This guide helps you migrate from the old JSON catalog system (`stable_diffusion.json`) to the new blockchain-based model registry using the ModelVault smart contract on Base Mainnet.

## What Changed?

### Before (JSON Catalog)
- Models listed in `stable_diffusion.json` hosted on GitHub
- Centralized model discovery
- Manual updates required
- Single point of failure
- No cryptographic verification

### After (Blockchain Registry)
- Models registered in ModelVault smart contract on Base Mainnet
- Decentralized model discovery
- Automatic updates from blockchain
- No single point of failure
- Cryptographic verification built-in

## Breaking Changes

### Removed

1. **`GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH`** environment variable
   - No longer needed - blockchain is the source
   - Remove from your `.env` file

2. **`stable_diffusion.json` dependency**
   - No longer downloaded or used
   - All model info comes from blockchain

3. **Git clone of model reference repository**
   - Removed from Docker build process
   - Reduces build time and dependencies

### Added

1. **`MODELVAULT_ENABLED`** - Enable blockchain registry (default: `true`)
2. **`MODELVAULT_RPC_URL`** - Base Mainnet RPC endpoint
3. **`MODELVAULT_CONTRACT`** - ModelVault contract address

## Migration Steps

### Step 1: Update Configuration

**Remove old config from `.env`:**
```bash
# DELETE THIS LINE:
GRID_IMAGE_MODEL_REFERENCE_REPOSITORY_PATH=../grid-image-model-reference
```

**Add new config to `.env` (if not already present):**
```bash
# Blockchain Model Registry (required)
MODELVAULT_ENABLED=true
MODELVAULT_RPC_URL=https://mainnet.base.org
MODELVAULT_CONTRACT=0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609
```

### Step 2: Update Code

Pull the latest changes:
```bash
git pull origin main
```

### Step 3: Rebuild Docker Images

```bash
# Clean rebuild to remove old dependencies
docker-compose build --no-cache

# Or quick rebuild if you trust cache
docker-compose build
```

### Step 4: Restart Services

```bash
docker-compose down
docker-compose up -d
```

### Step 5: Verify

Check logs to confirm blockchain connection:
```bash
docker-compose logs comfy-bridge | grep -i "blockchain\|modelvault"
```

You should see:
```
[INFO] ModelVault: Enabled (Base Mainnet)
[INFO] Loaded X models from blockchain
```

## Troubleshooting

### Issue: "No models resolved from WORKFLOW_FILE"

**Cause**: Models in your `.env` are not registered on blockchain

**Solution**:
1. Check which models are registered: View on BaseScan
2. Update `WORKFLOW_FILE` with blockchain-registered model names
3. Restart worker: `docker-compose restart comfy-bridge`

### Issue: "Error fetching total models: execution reverted"

**Cause**: Wrong network or contract address

**Solution**:
1. Verify you're using Base Mainnet (not Sepolia)
2. Check contract address is correct
3. Verify RPC URL is accessible

### Issue: "Blockchain client not available"

**Cause**: Missing `web3` Python package

**Solution**:
```bash
# Rebuild with updated dependencies
docker-compose build --no-cache comfy-bridge
```

### Issue: Models not downloading

**Cause**: Download URLs not registered on blockchain

**Solution**:
1. Check model registration includes download URLs
2. Models without URLs need to be re-registered
3. Contact model owner to update registration

## Model Name Changes

Some model names may have changed between JSON catalog and blockchain registry. Update your `.env` accordingly:

### Common Mappings

| Old Name (JSON) | New Name (Blockchain) |
|-----------------|----------------------|
| `flux1.dev` | `FLUX.1-dev` |
| `wan2_2_t2v_14b` | `wan2.2-t2v-a14b` |
| `wan2_2_ti2v_5b` | `wan2.2_ti2v_5B` |
| `sdxl` | `SDXL 1.0` |

**Note**: Check the actual blockchain registry for exact names. Names are case-sensitive!

## Verifying Migration

### 1. Check Blockchain Connection

```bash
docker-compose logs comfy-bridge | grep "ModelVault"
```

Expected output:
```
[INFO] ModelVault: Enabled (Base Mainnet)
[INFO] Loaded N models from blockchain
```

### 2. Check Model Discovery

```bash
docker-compose logs comfy-bridge | grep "ADVERTISING"
```

Expected output:
```
[INFO] 🚀 ADVERTISING N healthy models to Grid API:
[INFO]   1. ✓ 'FLUX.1-dev'
[INFO]   2. ✓ 'wan2.2-t2v-a14b'
```

### 3. Test Model Download

Open http://localhost:5000 and:
1. Browse available models
2. Verify models show blockchain verification ✅
3. Try downloading a model
4. Check download succeeds

### 4. Test Job Processing

1. Start hosting models
2. Wait for job assignment
3. Verify job processes successfully
4. Check logs for any errors

## Rollback (Emergency Only)

If you need to rollback to the old JSON catalog system:

```bash
# Checkout previous version
git checkout <previous-commit-hash>

# Rebuild
docker-compose build --no-cache

# Restart
docker-compose down
docker-compose up -d
```

**Note**: Rollback is not recommended as the JSON catalog is deprecated and may not receive updates.

## Benefits of Migration

### For Workers

- ✅ **Trustless**: No central authority controls model availability
- ✅ **Up-to-date**: Always see latest registered models
- ✅ **Verified**: Cryptographic verification of model authenticity
- ✅ **Transparent**: Anyone can verify model registrations

### For Users

- ✅ **Censorship-resistant**: No single entity can remove models
- ✅ **Authentic**: Verify models are legitimate
- ✅ **Discoverable**: Easy to find new models
- ✅ **Traceable**: Full history of model registrations

### For Developers

- ✅ **Decentralized**: No central server to maintain
- ✅ **Immutable**: Model data can't be arbitrarily changed
- ✅ **Programmable**: Smart contract enables automation
- ✅ **Extensible**: Easy to add new features on-chain

## FAQ

### Q: Do I need to register my own models?

A: No, you only host models that are already registered by model creators. Registration is done through the management UI or dedicated tools.

### Q: What if a model I want isn't on the blockchain?

A: Contact the model creator to register it, or register it yourself if you have the rights. The management UI provides tools for registration.

### Q: Can I still use models not on the blockchain?

A: Yes, if you have a valid workflow file. However, they won't be advertised to the Grid and won't receive jobs.

### Q: Is there a cost to query the blockchain?

A: No, reading from the blockchain is free. Only writing (registering models) requires gas fees.

### Q: What if the RPC endpoint is down?

A: Use an alternative RPC endpoint (see DEPLOYMENT.md). Base has multiple public endpoints.

### Q: How often does the worker refresh the model list?

A: The model list is cached and refreshed every hour, or when the worker restarts.

## Support

If you encounter issues during migration:

1. **Check Logs**: `docker-compose logs -f comfy-bridge`
2. **Verify Config**: Ensure `.env` has correct blockchain settings
3. **Test Connection**: Verify you can access Base Mainnet RPC
4. **GitHub Issues**: Report problems at https://github.com/AIPowerGrid/comfy-bridge/issues
5. **Documentation**: See BLOCKCHAIN.md and DEPLOYMENT.md for details

## Timeline

- **Old System (JSON)**: Deprecated as of December 2024
- **New System (Blockchain)**: Active and required
- **Support**: JSON catalog no longer maintained

## Next Steps

After successful migration:

1. ✅ Remove any local copies of `grid-image-model-reference`
2. ✅ Update your documentation/scripts
3. ✅ Monitor worker logs for any issues
4. ✅ Explore blockchain-registered models in the UI
5. ✅ Consider registering your own models

## Additional Resources

- **BLOCKCHAIN.md**: Detailed blockchain integration guide
- **DEPLOYMENT.md**: Production deployment instructions
- **README.md**: General setup and usage
- **BaseScan**: https://basescan.org/address/0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609
- **Base Docs**: https://docs.base.org

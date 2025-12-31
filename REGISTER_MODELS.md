# Registering Missing Models to Blockchain

## Overview

Some models need to be registered on the blockchain before they can be advertised to the Grid. This guide shows you how to register the missing models.

## Missing Models

The following models are currently missing from the blockchain:

1. **wan2.2-t2v-a14b** - WAN 2.2 Text-to-Video 14B model
2. **wan2.2-t2v-a14b-hq** - WAN 2.2 Text-to-Video 14B HQ model  
3. **ltxv** - LTX Video generation model

## Prerequisites

1. **Private Key**: You need a wallet with registrar role on the ModelVault contract
2. **ETH on Base**: Small amount of ETH on Base Mainnet for gas fees (~$0.50 per model)
3. **Python Packages**: `web3` and `eth-account`

```bash
pip install web3 eth-account
```

## Registration Script

### Option 1: Python Script (Recommended)

**Dry Run** (preview what will be registered):
```bash
python scripts/register_missing_models.py --dry-run
```

**Actual Registration**:
```bash
# Set your private key in .env
echo "PRIVATE_KEY=your_private_key_here" >> .env

# Register the models
python scripts/register_missing_models.py
```

### Option 2: JavaScript Script

```bash
# Install dependencies
npm install ethers dotenv

# Dry run
node scripts/register-models-to-chain.js --dry-run --model wan2.2-t2v-a14b

# Register specific model
node scripts/register-models-to-chain.js --model wan2.2-t2v-a14b

# Register all missing models
node scripts/register-models-to-chain.js
```

## What Gets Registered

For each model, the following information is registered on-chain:

- **Model Hash**: Keccak256 hash of filename (unique identifier)
- **Model Type**: VIDEO (2) for video generation models
- **File Name**: Primary model file name
- **Display Name**: Human-readable name shown in UI
- **Version**: Model version (e.g., "2.2", "0.9")
- **Download URL**: Where to download the model (if available)
- **Size**: Total size in bytes
- **Quantization**: fp8, fp16, etc.
- **Format**: safetensors, ckpt, etc.
- **VRAM**: Estimated VRAM requirement in MB
- **Base Model**: Architecture (wan_2_2, ltx_video, etc.)
- **Capabilities**: inpainting, img2img, controlnet, lora flags
- **NSFW**: Content rating flag

## Model Details

### wan2.2-t2v-a14b
```
Display Name: wan2.2-t2v-a14b
File Name: wan2.2_t2v_14B.safetensors
Type: VIDEO_MODEL
Size: ~26 GB
Quantization: fp8
VRAM: 48 GB
Base Model: wan_2_2
```

### wan2.2-t2v-a14b-hq
```
Display Name: wan2.2-t2v-a14b-hq
File Name: wan2.2_t2v_14B_hq.safetensors
Type: VIDEO_MODEL
Size: ~26 GB
Quantization: fp16
VRAM: 48 GB
Base Model: wan_2_2
```

### ltxv
```
Display Name: ltxv
File Name: ltx-video-2b-v0.9.safetensors
Type: VIDEO_MODEL
Size: ~4.8 GB
Quantization: fp16
VRAM: 24 GB
Base Model: ltx_video
Download URL: https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2b-v0.9.safetensors
```

## After Registration

Once models are registered on the blockchain:

1. **Restart Worker**: `docker-compose restart comfy-bridge`
2. **Verify**: Check logs for "Loaded X models from blockchain"
3. **Check Advertising**: Look for models in "ADVERTISING N healthy models" log
4. **Test**: Models should now appear in management UI and receive jobs

## Verification

### Check On-Chain

Visit BaseScan to verify registration:
```
https://basescan.org/address/0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609
```

### Check Worker Logs

```bash
docker-compose logs comfy-bridge | grep "ADVERTISING"
```

You should see all 8 models (5 currently registered + 3 newly registered):
```
ADVERTISING 8 healthy models to Grid API:
  1. FLUX.1-dev
  2. flux.1-krea-dev
  3. FLUX.1-dev-Kontext-fp8-scaled
  4. wan2.2_ti2v_5B
  5. Flux.1-Schnell fp8 (Compact)
  6. wan2.2-t2v-a14b           <- newly registered
  7. wan2.2-t2v-a14b-hq        <- newly registered
  8. ltxv                      <- newly registered
```

## Troubleshooting

### "PRIVATE_KEY required"

**Solution**: Add your private key to `.env`:
```bash
PRIVATE_KEY=0x1234567890abcdef...
```

**Security**: Never commit your private key to git! The `.env` file is in `.gitignore`.

### "Insufficient funds"

**Solution**: Add ETH to your wallet on Base Mainnet. Each registration costs ~$0.50 in gas.

### "execution reverted"

**Possible causes**:
1. Model already registered (check with `--dry-run`)
2. Wallet doesn't have registrar role
3. Contract address incorrect

### "Failed to connect to blockchain"

**Solution**: Check your internet connection and try alternative RPC:
```bash
MODELVAULT_RPC_URL=https://base.publicnode.com
```

## Cost Estimate

- **Gas per registration**: ~200,000 gas
- **Gas price**: ~0.01 gwei (Base is cheap!)
- **Cost per model**: ~$0.10 - $0.50
- **Total for 3 models**: ~$0.30 - $1.50

## Security Notes

1. **Private Key**: Keep your private key secure, never share it
2. **Registrar Role**: Only wallets with registrar role can register models
3. **Immutability**: Once registered, model data is permanent on-chain
4. **Verification**: Always verify model details before registering

## Alternative: Manual Registration

If you prefer to register via the management UI:

1. Open http://localhost:5000
2. Navigate to "Register Model" section
3. Fill in model details
4. Connect wallet with registrar role
5. Sign transaction

## Support

If you encounter issues:
- Check logs: `docker-compose logs comfy-bridge`
- Verify contract: https://basescan.org/address/0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609
- Report issues: https://github.com/AIPowerGrid/comfy-bridge/issues

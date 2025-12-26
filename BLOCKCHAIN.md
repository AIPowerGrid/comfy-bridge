# Blockchain Model Registry

## Overview

The AI Power Grid uses the **ModelVault smart contract** on **Base Mainnet** as the single source of truth for model registration and validation. This ensures transparency, security, and decentralization in the model discovery process.

## Key Concepts

### Single Source of Truth

All model information comes from the blockchain:
- **Model Names**: Display names and identifiers
- **Model Types**: Image, video, or text generation models
- **Download URLs**: Where to download model files
- **File Hashes**: SHA-256 hashes for verification
- **Constraints**: Valid parameter ranges (steps, CFG scale, samplers)
- **Metadata**: Descriptions, NSFW flags, capabilities

### Why Blockchain?

1. **Trustless Operation**: No central authority controls the model registry
2. **Transparency**: Anyone can verify model registrations on-chain
3. **Immutability**: Once registered, model data cannot be arbitrarily changed
4. **Censorship Resistance**: No single entity can remove models
5. **Authenticity**: Cryptographic verification of model files

## Architecture

### ModelVault Contract

**Network**: Base Mainnet  
**Chain ID**: 8453  
**Contract Address**: `0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609`  
**RPC URL**: https://mainnet.base.org

### Model Registration

Models are registered on-chain with the following information:

```solidity
struct Model {
    bytes32 modelHash;      // Unique identifier (keccak256 of filename)
    uint8 modelType;        // 0=Text, 1=Image, 2=Video
    string fileName;        // Primary file name
    string name;            // Display name
    string version;         // Model version
    string ipfsCid;         // IPFS content ID (optional)
    string downloadUrl;     // Primary download URL
    uint256 sizeBytes;      // Total size in bytes
    string quantization;    // Quantization type (fp16, fp8, int8, etc.)
    string format;          // File format/architecture
    uint256 vramMB;         // Estimated VRAM requirement in MB
    string baseModel;       // Base model architecture
    bool inpainting;        // Supports inpainting
    bool img2img;           // Supports image-to-image
    bool controlnet;        // Supports ControlNet
    bool lora;              // Is a LoRA model
    bool isActive;          // Currently active/available
    bool isNSFW;            // NSFW content flag
    uint256 timestamp;      // Registration timestamp
    address creator;        // Wallet address of registrant
}
```

### Model Constraints

Additional constraints can be registered for each model:

```solidity
struct ModelConstraints {
    uint16 stepsMin;              // Minimum steps
    uint16 stepsMax;              // Maximum steps
    uint16 cfgMinTenths;          // Min CFG scale * 10
    uint16 cfgMaxTenths;          // Max CFG scale * 10
    uint8 clipSkip;               // CLIP skip value
    bytes32[] allowedSamplers;    // Allowed sampler names
    bytes32[] allowedSchedulers;  // Allowed scheduler names
    bool exists;                  // Constraint exists flag
}
```

## Configuration

### Environment Variables

```bash
# Enable blockchain model registry (required)
MODELVAULT_ENABLED=true

# Base Mainnet RPC endpoint
MODELVAULT_RPC_URL=https://mainnet.base.org

# ModelVault contract address
MODELVAULT_CONTRACT=0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609
```

### Python Client

The `modelvault_client.py` module provides a Python interface to the blockchain:

```python
from comfy_bridge.modelvault_client import get_modelvault_client

# Get the client instance
client = get_modelvault_client(enabled=True)

# Fetch all registered models
models = client.fetch_all_models()

# Get specific model info
model_info = client.find_model("FLUX.1-dev")

# Validate job parameters against model constraints
validation = client.validate_params(
    file_name="flux1-dev-fp8.safetensors",
    steps=30,
    cfg=7.0,
    sampler="euler",
    scheduler="normal"
)
```

## Model Discovery Flow

1. **Worker Startup**: Client connects to Base Mainnet via RPC
2. **Fetch Registry**: Downloads all registered models from ModelVault contract
3. **Cache Models**: Stores model information in memory with TTL refresh
4. **Validate Jobs**: Checks incoming jobs against blockchain-registered models
5. **Download Models**: Uses blockchain-provided download URLs
6. **Verify Files**: Validates downloaded files against blockchain hashes

## Advantages Over JSON Catalogs

### Previous Approach (JSON)
- ❌ Centralized server hosts model list
- ❌ Single point of failure
- ❌ Can be censored or modified arbitrarily
- ❌ No cryptographic verification
- ❌ Requires trust in server operator

### Current Approach (Blockchain)
- ✅ Decentralized smart contract hosts model list
- ✅ No single point of failure (distributed blockchain)
- ✅ Censorship-resistant and immutable
- ✅ Cryptographic verification built-in
- ✅ Trustless - anyone can verify

## Adding Models to the Registry

Models can be registered by calling the ModelVault contract's registration functions. This typically requires:

1. **Model Files**: Prepared and uploaded to accessible storage (IPFS, Hugging Face, etc.)
2. **File Hashes**: SHA-256 hashes of all model files
3. **Metadata**: Complete model information (name, type, size, etc.)
4. **Gas Fees**: Small amount of ETH on Base Mainnet for transaction
5. **Wallet**: Connected wallet to sign the registration transaction

**Note**: Model registration is typically done through the management UI or dedicated registration tools.

## Troubleshooting

### RPC Connection Issues

If the client cannot connect to Base Mainnet:

1. **Check RPC URL**: Ensure `MODELVAULT_RPC_URL` is set correctly
2. **Try Alternative RPCs**: Base has multiple public RPC endpoints
3. **Check Network**: Verify your internet connection
4. **Firewall**: Ensure outbound HTTPS (443) is allowed

### Model Not Found

If a model shows as "not registered":

1. **Verify Name**: Check exact model name (case-sensitive)
2. **Check Contract**: Ensure correct contract address
3. **Refresh Cache**: Restart worker to reload model registry
4. **On-Chain Verification**: Check contract on Base block explorer

### Web3 Dependencies

The blockchain client requires `web3.py`:

```bash
pip install web3
```

If web3 is not available, the client falls back to disabled mode (no blockchain validation).

## Security Considerations

1. **RPC Trust**: You trust the RPC endpoint to provide accurate blockchain data
2. **Smart Contract**: The ModelVault contract code should be audited and verified
3. **Download URLs**: While registered on-chain, the actual file hosting is off-chain
4. **File Verification**: Always verify downloaded files against blockchain hashes
5. **Private Keys**: Never expose private keys - read-only operations don't require them

## Future Enhancements

- **IPFS Integration**: Decentralized file storage for models
- **Multi-Chain Support**: Deploy ModelVault on additional chains
- **Governance**: DAO-based model curation and dispute resolution  
- **Reputation System**: On-chain reputation for model uploaders
- **Automatic Updates**: Smart contract events for real-time model additions

## Resources

- **Base Mainnet Explorer**: https://basescan.org
- **Base Documentation**: https://docs.base.org
- **Web3.py Documentation**: https://web3py.readthedocs.io
- **ModelVault Contract**: View on BaseScan at `0x79F39f2a0eA476f53994812e6a8f3C8CFe08c609`

## Support

For issues related to blockchain integration:
- Check the logs for RPC connection errors
- Verify your network configuration
- Ensure `MODELVAULT_ENABLED=true` in `.env`
- Report persistent issues on GitHub with full error logs

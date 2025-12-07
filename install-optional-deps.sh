#!/bin/bash
# Script to install optional dependencies that may not be available

echo "🔧 Installing optional performance dependencies..."
echo "These packages enhance performance but are not required for core functionality."
echo ""

# Function to try installing a package
try_install() {
    local package=$1
    local description=$2

    echo "📦 Checking for $package..."
    if pip3 install --timeout 60 --quiet "$package" 2>/dev/null; then
        echo "  ✅ $package installed successfully ($description)"
        return 0
    else
        echo "  ⚠️  $package not available ($description)"
        return 1
    fi
}

# Try to install performance optimization packages
echo "🚀 Performance Optimizations:"
try_install "onnxruntime>=1.15.0" "ONNX Runtime for optimized model execution"
try_install "flash-attn>=2.0.0" "Flash Attention for memory-efficient attention"
try_install "sageattention>=1.0.0" "High-performance attention optimization"

# Try alternative flash attention packages
if ! pip3 show flash-attn >/dev/null 2>&1; then
    echo "📦 Checking for alternative flash attention..."
    if pip3 install --timeout 60 --quiet "flash-attention>=1.0.0" 2>/dev/null; then
        echo "  ✅ flash-attention installed successfully (alternative implementation)"
    fi
fi

echo ""
echo "🎯 Optional dependencies installation complete!"
echo "💡 Missing packages are normal and won't affect core ComfyUI functionality."
echo "   They only provide performance optimizations when available."
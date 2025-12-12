"""
Entry point for running comfy_bridge as a module.
Usage: python -m comfy_bridge
"""
import asyncio
import logging
import sys

# Configure logging BEFORE any imports that might create loggers
root_logger = logging.getLogger()

# Remove ALL existing handlers first
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
    handler.close()

# Create a single handler
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

# Disable propagation from child loggers to prevent duplicates
# All loggers should use the root handler
for name in list(logging.Logger.manager.loggerDict.keys()):
    logging.getLogger(name).handlers = []
    logging.getLogger(name).propagate = True

# Suppress noisy libraries
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)

# Now import after logging is configured
from .config import Settings
from .bridge import ComfyUIBridge

logger = logging.getLogger(__name__)


async def main():
    Settings.validate()
    
    bridge = ComfyUIBridge()
    try:
        await bridge.run()
    except asyncio.CancelledError:
        logger.info("Bridge run cancelled, shutting down...")
    finally:
        await bridge.cleanup()
        logger.info("Bridge cleanup complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting gracefully.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


import asyncio
import logging
import sys
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting gracefully.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

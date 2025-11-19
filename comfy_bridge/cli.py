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
    # Configure logging - prevent duplicates by ensuring exactly one handler
    root_logger = logging.getLogger()
    
    # Remove ALL existing handlers first
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()
    
    # Create a single handler with a custom filter to prevent duplicates
    class SingleHandlerFilter(logging.Filter):
        """Filter to prevent duplicate log messages"""
        def __init__(self):
            super().__init__()
            self.last_message = None
            self.last_time = None
        
        def filter(self, record):
            # Check if this is a duplicate of the last message
            msg = record.getMessage()
            now = record.created
            if msg == self.last_message and abs(now - (self.last_time or 0)) < 0.01:
                return False  # Suppress duplicate
            self.last_message = msg
            self.last_time = now
            return True
    
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    handler.addFilter(SingleHandlerFilter())
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    
    # Keep propagation enabled so child loggers work, but ensure only one handler
    root_logger.propagate = True
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting gracefully.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

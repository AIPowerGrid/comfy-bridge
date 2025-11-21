import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from comfy_bridge.cli import main


class TestCLI:
    """Test the CLI module."""

    @pytest.mark.asyncio
    async def test_main_success(self):
        """Test main function with successful execution."""
        with patch('comfy_bridge.cli.ComfyUIBridge') as mock_bridge_class:
            mock_bridge = MagicMock()
            mock_bridge.run = AsyncMock()
            mock_bridge.cleanup = AsyncMock()
            mock_bridge_class.return_value = mock_bridge

            await main()

            mock_bridge_class.assert_called_once()
            mock_bridge.run.assert_called_once()
            mock_bridge.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_cancellation(self):
        """Test main function with cancellation."""
        with patch('comfy_bridge.cli.ComfyUIBridge') as mock_bridge_class:
            mock_bridge = MagicMock()
            mock_bridge.run = AsyncMock(side_effect=asyncio.CancelledError())
            mock_bridge.cleanup = AsyncMock()
            mock_bridge_class.return_value = mock_bridge

            await main()  # Should handle cancellation gracefully

            mock_bridge.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_run_error(self):
        """Test main function with run error."""
        with patch('comfy_bridge.cli.ComfyUIBridge') as mock_bridge_class:
            mock_bridge = MagicMock()
            mock_bridge.run = AsyncMock(side_effect=Exception("Run failed"))
            mock_bridge.cleanup = AsyncMock()
            mock_bridge_class.return_value = mock_bridge

            with pytest.raises(Exception, match="Run failed"):
                await main()

            mock_bridge.cleanup.assert_called_once()
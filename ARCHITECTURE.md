# Architecture

## Overview

The bridge connects AI Power Grid to ComfyUI. Components are separated by responsibility for maintainability.

## Components

- **ComfyUIBridge**: Main orchestrator
- **APIClient**: Grid API communication
- **ComfyUIClient**: ComfyUI API wrapper
- **ResultProcessor**: Extracts media from outputs
- **PayloadBuilder**: Builds submission payloads
- **JobPoller**: Monitors workflow execution
- **R2Uploader**: Handles R2 storage uploads
- **FilesystemChecker**: Fallback file retrieval

## Design

- Dependency injection for testability
- Single responsibility per class
- Async/await for I/O operations
- Error handling with fallbacks

## Configuration

All settings via environment variables with sensible defaults.

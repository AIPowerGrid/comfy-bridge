# AI Power Grid Model Manager

Web-based management interface for the AI Power Grid ComfyUI Bridge worker.

## Features

- 🎨 Browse and filter AI models by compatibility, style, and VRAM requirements
- 📥 Download models with progress tracking
- 📦 View per-file download status with cancel/dismiss controls powered by SSE updates
- 🚀 Start/stop hosting models with one click
- 💻 Monitor GPU usage and disk space
- ⚙️ Configure API keys and worker settings
- 🔄 Restart containers and manage workflows

## Quick Start

### Web Interface

1. Ensure Docker containers are running:
   ```bash
   docker-compose up -d
   ```

2. Open http://localhost:5000 in your browser

### Desktop App (Electron)

**Development:**
```bash
npm install
npm run electron:dev
```

**Build:**
```bash
npm run electron:build
```

The built app will be in the `dist/` directory.

## Development

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

## Architecture

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling
- **Framer Motion** - Smooth animations
- **Electron** - Desktop app wrapper (optional)

## API Endpoints

All API routes are in `app/api/`:
- `/api/models` - List available models
- `/api/models/download` - Download a model
- `/api/models/host` - Start hosting a model
- `/api/gpu-info` - Get GPU information
- `/api/disk-space` - Get disk usage
- `/api/grid-config` - Manage worker configuration

## Building for Production

The app is containerized with Docker. See `Dockerfile` for details.

For Electron builds, use:
```bash
npm run electron:build
```

This creates platform-specific installers in `dist/`.

## License

MIT


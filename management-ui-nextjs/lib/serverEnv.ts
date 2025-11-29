/**
 * Server environment utilities and configuration
 */

// Get the base URL for the downloads API
export function downloadsApiUrl(path: string = ''): string {
  // Use environment variable or default to localhost
  const baseUrl = process.env.DOWNLOADS_API_URL || 'http://localhost:8002';
  return `${baseUrl}${path}`;
}

// Get the base URL for the ComfyUI API
export function comfyUiApiUrl(path: string = ''): string {
  // Use environment variable or default to localhost
  const baseUrl = process.env.COMFYUI_API_URL || 'http://localhost:8188';
  return `${baseUrl}${path}`;
}

// Get the base URL for the GPU info API
export function gpuInfoApiUrl(path: string = ''): string {
  // Use environment variable or default to localhost
  const baseUrl = process.env.GPU_INFO_API_URL || 'http://localhost:8001';
  return `${baseUrl}${path}`;
}

// Get environment variable with fallback
export function getEnvVar(key: string, defaultValue: string = ''): string {
  return process.env[key] || defaultValue;
}

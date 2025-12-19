'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import GPUInfo from '@/components/GPUInfo';
import DiskSpace from '@/components/DiskSpace';
// ModelDetailView removed - blockchain registry is now the primary model UI
import Header from '@/components/Header';
import StatusMessage from '@/components/StatusMessage';
import APIKeyEditor from '@/components/APIKeyEditor';
import APIKeyStatus from '@/components/APIKeyStatus';
import GettingStartedGuide from '@/components/GettingStartedGuide';
import GridConfigEditor from '@/components/GridConfigEditor';
import RestartCountdown from '@/components/RestartCountdown';
import RemovalSummaryDialog from '@/components/RemovalSummaryDialog';
import RebuildingPage from '@/components/RebuildingPage';
import { ToastContainer } from '@/components/Toast';
import { useToast } from '@/lib/useToast';
import { ModelVaultStatus } from '@/components/ModelVaultStatus';
import { useModelVaultRegister, generateModelHash, ModelType } from '@/lib/web3';
import type { RegisterModelParams } from '@/lib/web3';

export default function Home() {
  const [gpuInfo, setGpuInfo] = useState<any>(null);
  const [diskSpace, setDiskSpace] = useState<any>(null);
  // Note: catalog removed - blockchain registry is now the single source of truth
  const [apiKeys, setApiKeys] = useState<any>({ huggingface: '', civitai: '' });
  const [gridConfig, setGridConfig] = useState<any>({ gridApiKey: '', workerName: '', aipgWallet: '' });
  // Note: filter and styleFilter removed - filtering is now handled by ModelVaultStatus component
  const [loading, setLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState<{type: 'success' | 'error' | 'info', message: string} | null>(null);
  const [downloadStatus, setDownloadStatus] = useState<any>(null);
  const [showGettingStarted, setShowGettingStarted] = useState(false);
  const [isModelVaultCollapsed, setIsModelVaultCollapsed] = useState(false);
  const [isApiKeysCollapsed, setIsApiKeysCollapsed] = useState(false);
  const [isGpuInfoCollapsed, setIsGpuInfoCollapsed] = useState(false);
  const [isDiskSpaceCollapsed, setIsDiskSpaceCollapsed] = useState(false);
  const [isGridConfigCollapsed, setIsGridConfigCollapsed] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);
  const [showRestartCountdown, setShowRestartCountdown] = useState(false);
  const [showRebuildingPage, setShowRebuildingPage] = useState(false);
  const [restartMessage, setRestartMessage] = useState('Containers will restart');
  const [showRemovalDialog, setShowRemovalDialog] = useState(false);
  const [removalItems, setRemovalItems] = useState<any[]>([]);
  const [pendingRestartAction, setPendingRestartAction] = useState<(() => void) | null>(null);
  
  // Toast notifications
  const { toasts, removeToast, showSuccess, showError, showInfo, showWarning } = useToast();

  // ModelVault registration
  const { registerModel, isRegistering, isConnected: isWalletConnected } = useModelVaultRegister();
  const [registeredModelHashes, setRegisteredModelHashes] = useState<Set<string>>(new Set());
  const [registeringModelId, setRegisteringModelId] = useState<string | null>(null);
  
  // Model status for blockchain registry
  const [installedModels, setInstalledModels] = useState<Set<string>>(new Set());
  const [hostedModels, setHostedModels] = useState<Set<string>>(new Set());

  useEffect(() => {
    // Set a failsafe timeout to ensure loading state clears even if API calls hang
    const failsafeTimeout = setTimeout(() => {
      setLoading(false);
    }, 15000);

    loadData().finally(() => {
      clearTimeout(failsafeTimeout);
    });
    
    // Disabled: Run startup cleanup to remove orphaned WORKFLOW_FILE entries
    // runStartupCleanup();
    
    // Set up custom event listener for toast notifications from Header component
    const handleToastEvent = (event: CustomEvent) => {
      const { type, title, message } = event.detail;
      if (type === 'error') {
        showError(title, message);
      } else if (type === 'success') {
        showSuccess(title, message);
      } else if (type === 'warning') {
        showWarning(title, message);
      } else {
        showInfo(title, message);
      }
    };
    
    window.addEventListener('showToast', handleToastEvent as EventListener);
    
    // Set up SSE connection for real-time download updates (only if endpoint exists)
    let eventSource: EventSource | null = null;
    let fallbackInterval: NodeJS.Timeout | null = null;
    
    // Check if SSE endpoint exists before connecting
    fetch('/api/models/download/stream', { method: 'HEAD' })
      .then(res => {
        if (res.ok || res.status === 405) {
          // Endpoint exists, set up SSE
          eventSource = new EventSource('/api/models/download/stream');
          
          eventSource.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              if (data.type === 'status') {
                setDownloadStatus(data);
              }
            } catch (error) {
              console.error('Error parsing SSE data:', error);
            }
          };
          
          eventSource.onerror = () => {
            console.log('SSE connection closed or errored');
            eventSource?.close();
          };
        }
      })
      .catch(() => {
        // SSE endpoint doesn't exist, that's OK - downloads will work without live updates
        console.log('Download stream endpoint not available');
      });
    
    return () => {
      clearTimeout(failsafeTimeout);
      eventSource?.close();
      if (fallbackInterval) clearInterval(fallbackInterval);
      window.removeEventListener('showToast', handleToastEvent as EventListener);
    };
  }, []);

  const runStartupCleanup = async () => {
    try {
      const response = await fetch('/api/startup-cleanup');
      const result = await response.json();
      
      if (result.success && result.requires_restart) {
        console.log('Orphaned workflow entries found and cleaned. Restart needed.');
        // Don't automatically restart on startup, just log
      }
    } catch (error) {
      console.error('Startup cleanup failed:', error);
    }
  };
  
  const loadModelStatus = async () => {
    try {
      const response = await fetch('/api/models-status');
      if (response.ok) {
        const data = await response.json();
        setHostedModels(new Set(data.hostedModels || []));
        // Create set of installed model names from filenames
        const installedSet = new Set<string>();
        for (const file of (data.installedFiles || [])) {
          // Remove extension and add variations
          const baseName = file.replace(/\.(safetensors|ckpt|pt)$/i, '');
          installedSet.add(file);
          installedSet.add(baseName);
          installedSet.add(baseName.replace(/_/g, '-'));
          installedSet.add(baseName.replace(/-/g, '_'));
        }
        setInstalledModels(installedSet);
      }
    } catch (error) {
      console.error('Failed to load model status:', error);
    }
  };

  const loadData = async () => {
    // Helper function to fetch with timeout
    const fetchWithTimeout = async (url: string, timeoutMs: number = 5000) => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);
        return response;
      } catch (error: any) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
          throw new Error(`Request to ${url} timed out`);
        }
        throw error;
      }
    };

    try {
      // Load model status (for blockchain registry display)
      await loadModelStatus();
      
      // Load data in parallel with timeouts
      // Note: models-catalog removed - blockchain registry is the source of truth
      const [gpuRes, diskRes, keysRes, gridRes] = await Promise.allSettled([
        fetchWithTimeout('/api/gpu-info'),
        fetchWithTimeout('/api/disk-space'),
        fetchWithTimeout('/api/api-keys'),
        fetchWithTimeout('/api/grid-config'),
      ]);

      // Process GPU info
      if (gpuRes.status === 'fulfilled' && gpuRes.value.ok) {
        setGpuInfo(await gpuRes.value.json());
      } else {
        console.warn('GPU info failed:', gpuRes.status === 'rejected' ? gpuRes.reason : 'Bad response');
        setGpuInfo({ available: false, gpus: [], total_memory_gb: 0 });
      }

      // Process disk space
      if (diskRes.status === 'fulfilled' && diskRes.value.ok) {
        setDiskSpace(await diskRes.value.json());
      } else {
        console.warn('Disk space failed:', diskRes.status === 'rejected' ? diskRes.reason : 'Bad response');
        setDiskSpace({ error: 'Failed to load disk space' });
      }

      // Process API keys
      if (keysRes.status === 'fulfilled' && keysRes.value.ok) {
        setApiKeys(await keysRes.value.json());
      } else {
        console.warn('API keys failed:', keysRes.status === 'rejected' ? keysRes.reason : 'Bad response');
      }

      // Process grid config
      if (gridRes.status === 'fulfilled' && gridRes.value.ok) {
        setGridConfig(await gridRes.value.json());
      } else {
        console.warn('Grid config failed:', gridRes.status === 'rejected' ? gridRes.reason : 'Bad response');
      }

      setLoading(false);
    } catch (error) {
      console.error('Failed to load data:', error);
      showStatus('error', 'Failed to load data');
      showError('Data Loading Error', 'Failed to load application data. Please refresh the page.');
      setLoading(false);
    }
  };

  const showStatus = (type: 'success' | 'error' | 'info', message: string) => {
    setStatusMessage({ type, message });
    setTimeout(() => setStatusMessage(null), 5000);
  };

  const toggleAllCollapsed = () => {
    const allCollapsed = isModelVaultCollapsed && isApiKeysCollapsed && isGpuInfoCollapsed && isDiskSpaceCollapsed && isGridConfigCollapsed;
    setIsModelVaultCollapsed(!allCollapsed);
    setIsApiKeysCollapsed(!allCollapsed);
    setIsGpuInfoCollapsed(!allCollapsed);
    setIsDiskSpaceCollapsed(!allCollapsed);
    setIsGridConfigCollapsed(!allCollapsed);
  };


  const handleSaveAPIKeys = async (keys: { huggingface: string; civitai: string }) => {
    try {
      showStatus('info', 'Saving API keys and restarting containers...');
      
      const res = await fetch('/api/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(keys),
      });
      
      const result = await res.json();
      
      if (!res.ok) throw new Error(result.error || 'Failed to save API keys');
      
      setApiKeys(keys);
      
      if (result.warning) {
        showStatus('error', result.message + ' ' + result.warning);
        showWarning('Container Restart Failed', result.warning);
      } else {
        showStatus('success', result.message);
        showSuccess('API Keys Saved', 'API keys saved and containers restarted successfully!');
      }
    } catch (error: any) {
      showStatus('error', 'Failed to save API keys: ' + error.message);
      showError('Save Failed', 'Failed to save API keys: ' + error.message);
      throw error;
    }
  };

  const handleSaveGridConfig = async (config: { gridApiKey: string; workerName: string; aipgWallet: string }) => {
    try {
      showStatus('info', 'Saving configuration and restarting containers...');
      
      const res = await fetch('/api/grid-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      
      const result = await res.json();
      
      if (!res.ok) throw new Error(result.error || 'Failed to save grid configuration');
      
      setGridConfig(config);
      
      if (result.warning) {
        showStatus('error', result.message + ' ' + result.warning);
        showWarning('Container Restart Failed', result.warning);
      } else {
        showStatus('success', result.message);
        showSuccess('Configuration Saved', 'Grid configuration saved and containers restarted successfully!');
      }
    } catch (error: any) {
      showStatus('error', 'Failed to save grid configuration: ' + error.message);
      showError('Save Failed', 'Failed to save grid configuration: ' + error.message);
      throw error;
    }
  };

  const handleHost = async (modelId: string) => {
    try {
      showStatus('info', `Starting to host ${modelId}...`);
      
      const res = await fetch('/api/models/host', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId }),
      });
      
      const result = await res.json();
      
      if (result.success) {
        if (result.requires_restart) {
          // Show countdown for restart
          setRestartMessage(`${modelId} is now hosted! Containers will restart to start earning`);
          setShowRestartCountdown(true);
        } else if (result.already_hosted) {
          showStatus('success', `${modelId} is already being hosted!`);
          showSuccess('Already Hosted', result.message || `${modelId} is already configured for hosting.`);
          await loadData();
        } else {
          showStatus('success', `Now hosting ${modelId}!`);
          showSuccess('Model Hosting Started', result.message || `${modelId} is now being hosted!`);
          await loadData();
        }
      } else {
        // Check if this is a missing models error
        if (result.missing_models && result.missing_models.length > 0) {
          const missingList = result.missing_models
            .map((m: { filename: string; loader: string }) => m.filename)
            .join(', ');
          showStatus('error', `Missing model files: ${missingList}`);
          showError(
            'Missing Required Models', 
            `Cannot host ${modelId}. Please download and install the required model files first:\n\n${result.missing_models.map((m: { filename: string; loader: string }) => `• ${m.filename}`).join('\n')}`
          );
        } else {
          showStatus('error', 'Failed to start hosting: ' + (result.error || 'Unknown error'));
          showError('Hosting Failed', 'Failed to start hosting: ' + (result.error || 'Unknown error'));
        }
      }
    } catch (error: any) {
      showStatus('error', 'Error: ' + error.message);
      showError('Hosting Error', 'Error: ' + error.message);
    }
  };

  const handleUnhost = async (modelId: string) => {
    try {
      showStatus('info', `Stopping hosting of ${modelId}...`);
      const res = await fetch('/api/models/unhost', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId }),
      });
      
      const result = await res.json();
      
      if (result.success && result.restarted) {
        // Show countdown for restart
        setRestartMessage(`Stopped hosting ${modelId}. Containers will restart`);
        setShowRestartCountdown(true);
      } else if (result.success) {
        showStatus('success', `Stopped hosting ${modelId}!`);
        showSuccess('Model Hosting Stopped', result.message);
        await loadData();
      } else {
        showStatus('error', 'Failed to stop hosting: ' + (result.error || 'Unknown error'));
        showError('Stop Hosting Failed', 'Failed to stop hosting: ' + (result.error || 'Unknown error'));
      }
    } catch (error: any) {
      showStatus('error', 'Error: ' + error.message);
      showError('Stop Hosting Error', 'Error: ' + error.message);
    }
  };

  const handleDownloadSingle = async (modelId: string, autoHost: boolean = false) => {
    try {
      // For blockchain models, we fetch from the chain - no local catalog needed
      showStatus('info', `Starting download of ${modelId}...`);
      
      // Set initial download status to show the progress indicator
      setDownloadStatus({
        is_downloading: true,
        current_model: modelId,
        progress: 0,
        speed: '',
        eta: '',
        message: 'Starting download...'
      });

      // Start download - read SSE stream for progress
      const downloadRes = await fetch('/api/models/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          models: [modelId],
        }),
      });

      if (!downloadRes.ok) {
        setDownloadStatus(null);
        throw new Error(`Download failed: ${downloadRes.status}`);
      }

      // Read the SSE stream for completion
      const reader = downloadRes.body?.getReader();
      if (reader) {
        const decoder = new TextDecoder();
        let buffer = '';
        
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  const targetModel = data.model || modelId;
                  
                  // Update download status for progress display
                  if (data.type === 'info' || data.type === 'progress') {
                    setDownloadStatus((prev: any) => ({
                      is_downloading: true,
                      current_model: targetModel,
                      progress: data.progress ?? prev?.progress ?? 0,
                      speed: data.speed || prev?.speed || '',
                      eta: data.eta || prev?.eta || '',
                      message: data.message || prev?.message || 'Downloading...'
                    }));
                  } else if (data.type === 'start') {
                    setDownloadStatus({
                      is_downloading: true,
                      current_model: targetModel,
                      progress: 0,
                      speed: '',
                      eta: '',
                      message: data.message || 'Starting download...'
                    });
                  } else if (data.type === 'success') {
                    // File completed, update message but keep downloading
                    setDownloadStatus((prev: any) => ({
                      ...prev,
                      message: data.message || 'File downloaded successfully'
                    }));
                  } else if (data.type === 'warning') {
                    // Warning message, keep downloading
                    setDownloadStatus((prev: any) => ({
                      ...prev,
                      message: data.message || 'Warning during download'
                    }));
                  } else if (data.type === 'complete') {
                    // Clear download status
                    setDownloadStatus(null);
                    
                    if (autoHost) {
                      showStatus('success', `${targetModel} installed successfully! Starting hosting...`);
                      showSuccess('Download Complete', `${targetModel} installed successfully! Preparing to start earning...`);
                      // handleHost will show the countdown modal
                      await handleHost(targetModel);
                    } else {
                      showStatus('success', `${targetModel} installed successfully! Click "Start Earning" to begin making money.`);
                      showSuccess('Download Complete', `${targetModel} installed successfully! Click "Start Earning" to begin making money.`);
                      await loadData();
                    }
                  } else if (data.type === 'error') {
                    setDownloadStatus(null);
                    throw new Error(data.message);
                  }
                } catch (e) {
                  if (e instanceof Error && e.message !== 'Error parsing SSE:') {
                    throw e;
                  }
                  console.error('Error parsing SSE:', e);
                }
              }
            }
          }
        } catch (readError) {
          console.error('Error reading stream:', readError);
          setDownloadStatus(null);
          throw readError;
        }
      }
    } catch (error: any) {
      setDownloadStatus(null);
      showStatus('error', 'Error: ' + error.message);
      showError('Download Error', 'Error: ' + error.message);
    }
  };

  const handleCancelDownload = async (modelId?: string) => {
    try {
      if (!modelId) {
        showStatus('error', 'No model specified for cancellation');
        return;
      }
      
      const response = await fetch('/api/models/download/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId }),
      });
      
      const result = await response.json();
      
      if (result.success) {
        showStatus('info', 'Download cancelled successfully');
        showSuccess('Download Cancelled', `Stopped download for ${modelId}`);
        loadData(); // Reload to update status
      } else {
        showStatus('error', `Failed to cancel download: ${result.error || 'Unknown error'}`);
        showError('Cancel Failed', result.error || 'Unknown error');
      }
    } catch (error: any) {
      showStatus('error', `Error cancelling download: ${error.message}`);
      showError('Cancel Error', error.message);
    }
  };

  const handleUninstall = async (modelId: string) => {
    await handleBatchUninstall([modelId]);
  };

  const handleBatchUninstall = async (modelIds: string[]) => {
    try {
      const modelCount = modelIds.length;
      showStatus('info', `Preparing to uninstall ${modelCount} model${modelCount > 1 ? 's' : ''}...`);
      
      const res = await fetch('/api/models/uninstall', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_ids: modelIds }),
      });
      
      const result = await res.json();
      
      if (result.success) {
        // Check for affected models (shared files case)
        const affectedModels = result.affected_models || modelIds;
        
        if (result.removed_items && result.removed_items.length > 0) {
          // Show removal summary dialog if files were deleted
          const items = (result.removed_items || []).map((item: any) => ({
            name: item.name,
            type: item.type,
            size: item.size ? `${(item.size / 1024 / 1024 / 1024).toFixed(2)} GB` : undefined
          }));
          
          setRemovalItems(items);
          setShowRemovalDialog(true);
          
          // Set up the restart action
          const restartMsg = `Uninstalled ${affectedModels.length} model${affectedModels.length > 1 ? 's' : ''}: ${affectedModels.slice(0, 3).join(', ')}${affectedModels.length > 3 ? '...' : ''}. Containers will restart`;
          
          setPendingRestartAction(() => async () => {
            setShowRemovalDialog(false);
            setRestartMessage(restartMsg);
            setShowRestartCountdown(true);
          });
        } else if (result.requires_restart) {
          // No files removed but configuration changed, go straight to countdown
          const msg = `Removed ${affectedModels.length} model${affectedModels.length > 1 ? 's' : ''} from hosting configuration.`;
          showSuccess('Configuration Cleaned', msg);
          setRestartMessage(`${msg} Containers will restart`);
          setShowRestartCountdown(true);
        } else {
          // Nothing to do
          showInfo('No Action Needed', result.message);
          await loadData();
        }
      } else {
        showStatus('error', 'Removal failed: ' + (result.error || 'Unknown error'));
        showError('Removal Failed', result.error);
      }
    } catch (error: any) {
      showStatus('error', 'Error: ' + error.message);
      showError('Uninstall Error', error.message);
    }
  };

  // Register model to ModelVault on-chain
  const handleRegisterToVault = async (modelId: string, model: any) => {
    if (!isWalletConnected) {
      showError('Wallet Not Connected', 'Please connect your wallet to register models on-chain');
      return;
    }

    try {
      setRegisteringModelId(modelId);
      showStatus('info', `Registering ${model.display_name || modelId} to ModelVault...`);

      // Determine model type based on baseline/style
      // ModelType: TEXT_MODEL = 0, IMAGE_MODEL = 1, VIDEO_MODEL = 2
      let modelType = ModelType.IMAGE_MODEL; // Default to image
      const baseline = (model.baseline || '').toLowerCase();
      const style = (model.style || '').toLowerCase();
      
      if (baseline.includes('video') || baseline.includes('wan') || baseline.includes('ltx') || 
          model.capability_type?.includes('Video') || style.includes('video')) {
        modelType = ModelType.VIDEO_MODEL;
      } else if (baseline.includes('llm') || baseline.includes('text') || baseline.includes('language')) {
        modelType = ModelType.TEXT_MODEL;
      } else {
        // All image models (SD, SDXL, FLUX, etc.) use IMAGE_MODEL
        modelType = ModelType.IMAGE_MODEL;
      }

      const fileName = model.config?.files?.[0]?.path || model.filename || modelId;
      // Calculate sizeBytes as number - the registerModel function accepts both number and bigint
      // and will normalize internally. This ensures compatibility across different TypeScript environments.
      const sizeBytesValue: number | bigint = Math.floor((model.size_gb || 0) * 1024 * 1024 * 1024);

      const result = await (registerModel as (modelData: RegisterModelParams) => Promise<{ success: boolean; error?: string }>)({
        modelId,
        fileName,
        displayName: model.display_name || model.name || modelId,
        description: model.description || '',
        modelType,
        isNSFW: model.nsfw || false,
        sizeBytes: sizeBytesValue,
        inpainting: model.inpainting || false,
        img2img: false,
        controlnet: false,
        lora: model.type === 'loras',
        baseModel: model.baseline || '',
        architecture: model.type || 'checkpoints',
      });

      if (result.success) {
        showSuccess('Model Registered', `${model.display_name || modelId} has been registered on-chain!`);
        // Add to registered hashes
        const hash = generateModelHash(fileName);
        setRegisteredModelHashes(prev => new Set([...prev, hash]));
      } else {
        showError('Registration Failed', result.error || 'Failed to register model');
      }
    } catch (error: any) {
      console.error('Registration error:', error);
      showError('Registration Error', error.message || 'An error occurred during registration');
    } finally {
      setRegisteringModelId(null);
    }
  };
  
  const handleRestartComplete = async () => {
    try {
      setShowRestartCountdown(false);
      setShowRebuildingPage(true);
      
      // Call the restart API
      const res = await fetch('/api/containers/restart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      
      if (!res.ok) {
        const result = await res.json();
        showError('Restart Failed', result.error || 'Failed to restart containers');
        setShowRebuildingPage(false);
      }
      // If successful, the RebuildingPage component will handle the rest
    } catch (error: any) {
      showError('Restart Error', error.message);
      setShowRebuildingPage(false);
    }
  };
  
  const handleRebuildComplete = () => {
    // Called when RebuildingPage detects containers are back up
    setTimeout(() => {
      window.location.reload();
    }, 500);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-aipg-orange border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-xl text-white">Loading AI Power Grid...</p>
          <p className="text-sm text-gray-400 mt-2">Setting up your worker dashboard</p>
        </div>
      </div>
    );
  }

  // Calculate API key requirements (blockchain models may require API keys for downloads)
  const modelsRequiringKeys = {
    huggingface: 0, // Will be determined from blockchain model metadata when needed
    civitai: 0,
  };

  // Show rebuilding page if containers are rebuilding
  if (showRebuildingPage) {
    return (
      <RebuildingPage 
        message="Rebuilding and restarting containers"
        onComplete={handleRebuildComplete}
      />
    );
  }
  
  return (
    <div className="min-h-screen bg-black text-white">
      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
      
      {/* Restart Indicator Overlay */}
      {isRestarting && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center">
          <div className="bg-gray-900 rounded-xl border border-gray-700 p-8 max-w-md">
            <div className="flex flex-col items-center gap-4">
              <div className="w-16 h-16 border-4 border-aipg-orange border-t-transparent rounded-full animate-spin"></div>
              <h3 className="text-2xl font-bold text-white">Restarting Containers</h3>
              <p className="text-gray-400 text-center">
                Containers are restarting to apply your changes. This may take a few moments...
              </p>
            </div>
          </div>
        </div>
      )}
      
      {/* Getting Started Guide Modal */}
      {showGettingStarted && (
        <GettingStartedGuide onClose={() => setShowGettingStarted(false)} />
      )}

      <div className="container mx-auto px-6 py-8">
        <Header />
        
        {/* Getting Started Button */}
        <div className="text-center mb-8">
          <button
            onClick={() => setShowGettingStarted(true)}
            className="inline-flex items-center gap-2 px-6 py-3 bg-aipg-orange text-white rounded-lg font-semibold hover:bg-aipg-orange/90 transition-all"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            New to AI Power Grid? Start Here
          </button>
        </div>
        
        {statusMessage && (
          <StatusMessage type={statusMessage.type} message={statusMessage.message} />
        )}

        {/* Global Download Status Banner */}
        {downloadStatus?.is_downloading && (
          <motion.div
            initial={{ opacity: 0, y: -50 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-r from-yellow-600/20 to-orange-600/20 border border-yellow-500/50 rounded-xl p-4 mb-6"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 bg-yellow-500 rounded-full animate-pulse"></div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-yellow-400">Download in Progress</h3>
                  <p className="text-sm text-gray-400">
                    {downloadStatus.current_model ? 
                      `Downloading ${downloadStatus.current_model}` : 
                      'Download in progress...'
                    }
                  </p>
                  {/* Show current file being downloaded */}
                  {downloadStatus.message && (
                    <p className="text-xs text-gray-500 mt-1 truncate max-w-md" title={downloadStatus.message}>
                      {downloadStatus.message}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-4">
                {downloadStatus.progress > 0 && (
                  <div className="text-right">
                    <div className="text-sm font-semibold text-yellow-400">
                      {downloadStatus.progress.toFixed(1)}%
                    </div>
                    {downloadStatus.speed && (
                      <div className="text-xs text-gray-400">
                        {downloadStatus.speed}
                      </div>
                    )}
                    {downloadStatus.eta && (
                      <div className="text-xs text-gray-500">
                        ETA: {downloadStatus.eta}
                      </div>
                    )}
                  </div>
                )}
                <button
                  onClick={() => handleCancelDownload(downloadStatus?.model)}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-all flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  Cancel
                </button>
              </div>
            </div>
            {downloadStatus.progress > 0 && (
              <div className="mt-3">
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div 
                    className="bg-gradient-to-r from-yellow-500 to-orange-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${downloadStatus.progress}%` }}
                  ></div>
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* Expand/Collapse All Button */}
        <div className="flex justify-center mb-6">
          <button
            onClick={toggleAllCollapsed}
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 text-gray-300 rounded-lg font-medium hover:bg-gray-700 transition-all border border-gray-600"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
            {isModelVaultCollapsed && isApiKeysCollapsed && isGpuInfoCollapsed && isDiskSpaceCollapsed && isGridConfigCollapsed ? 'Expand All' : 'Collapse All'}
          </button>
        </div>

        {/* Main Content */}
        <div className="space-y-8">
          
          {/* System Info - Full width on mobile, sidebar on desktop */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GPUInfo 
              gpuInfo={gpuInfo} 
              isCollapsed={isGpuInfoCollapsed}
              onToggleCollapse={() => setIsGpuInfoCollapsed(!isGpuInfoCollapsed)}
            />
            <DiskSpace 
              diskSpace={diskSpace} 
              isCollapsed={isDiskSpaceCollapsed}
              onToggleCollapse={() => setIsDiskSpaceCollapsed(!isDiskSpaceCollapsed)}
            />
          </div>

          {/* Configuration Area - Grid Config and API Keys side by side */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Grid Configuration */}
            <GridConfigEditor
              gridApiKey={gridConfig.gridApiKey || ''}
              workerName={gridConfig.workerName || ''}
              aipgWallet={gridConfig.aipgWallet || ''}
              onSave={handleSaveGridConfig}
              isCollapsed={isGridConfigCollapsed}
              onToggleCollapsed={() => setIsGridConfigCollapsed(!isGridConfigCollapsed)}
            />
            
            {/* API Keys Section */}
            <div className="bg-gray-900 rounded-xl border border-gray-700">
              {/* Collapsible Header */}
              <div
                className="flex items-center justify-between p-6 cursor-pointer hover:bg-gray-800/30 transition-colors"
                onClick={() => setIsApiKeysCollapsed(!isApiKeysCollapsed)}
              >
                <div className="flex items-center gap-3">
                  <svg className="w-6 h-6 text-aipg-orange" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                  </svg>
                  <div>
                    <h2 className="text-xl font-bold text-white">API Keys Setup</h2>
                    <p className="text-sm text-gray-400">
                      {apiKeys.huggingface || apiKeys.civitai ? '✓ API keys configured' : 'Configure API keys for model downloads'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {(apiKeys.huggingface || apiKeys.civitai) && (
                    <span className="px-3 py-1 text-xs bg-green-500/20 text-green-400 rounded-full border border-green-500/50">
                      Configured
                    </span>
                  )}
                  <svg
                    className={`w-5 h-5 text-gray-400 transition-transform ${isApiKeysCollapsed ? 'rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>

              {/* Collapsible Content */}
              <motion.div
                initial={false}
                animate={{ height: isApiKeysCollapsed ? 0 : 'auto' }}
                transition={{ duration: 0.3 }}
                className="overflow-hidden"
              >
                <div className="px-6 pb-6">
                  <APIKeyEditor
                    huggingfaceKey={apiKeys.huggingface || ''}
                    civitaiKey={apiKeys.civitai || ''}
                    onSave={handleSaveAPIKeys}
                  />
                </div>
              </motion.div>
            </div>
          </div>
          
          {/* API Key Warning */}
          <APIKeyStatus
            hasHuggingFaceKey={!!apiKeys.huggingface}
            hasCivitaiKey={!!apiKeys.civitai}
            modelsRequiringKeys={modelsRequiringKeys}
          />
          
          {/* Blockchain Model Registry */}
          <ModelVaultStatus 
            onStartEarning={async (modelName) => {
              // This callback is only called for installed models (the component handles the check)
              // Just start hosting directly
              await handleHost(modelName);
            }}
            onStopEarning={async (modelName) => {
              await handleUnhost(modelName);
            }}
            onUninstall={async (modelName) => {
              await handleUninstall(modelName);
            }}
            onBatchUninstall={async (modelNames) => {
              await handleBatchUninstall(modelNames);
            }}
            onDownload={async (modelName) => {
              // Download and auto-host
              await handleDownloadSingle(modelName, true);
            }}
            installedModels={installedModels}
            hostedModels={hostedModels}
            downloadingModels={new Set(
              downloadStatus?.is_downloading && downloadStatus?.current_model ? [downloadStatus.current_model] : []
            )}
            isCollapsed={isModelVaultCollapsed}
            onToggleCollapse={() => setIsModelVaultCollapsed(!isModelVaultCollapsed)}
          />
        </div>
      </div>
      
      {/* Restart Countdown Modal */}
      <RestartCountdown
        isVisible={showRestartCountdown}
        onComplete={handleRestartComplete}
        message={restartMessage}
        countdown={5}
      />
      
      {/* Removal Summary Dialog */}
      <RemovalSummaryDialog
        isOpen={showRemovalDialog}
        items={removalItems}
        onConfirm={() => {
          if (pendingRestartAction) {
            pendingRestartAction();
          }
        }}
        onCancel={() => {
          setShowRemovalDialog(false);
          setRemovalItems([]);
          setPendingRestartAction(null);
        }}
        title="Uninstall Complete"
        confirmText="OK, Restart Containers"
      />
      
      {/* Toast Container */}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </div>
  );
}
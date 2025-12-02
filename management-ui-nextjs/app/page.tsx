'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import GPUInfo from '@/components/GPUInfo';
import DiskSpace from '@/components/DiskSpace';
import ModelDetailView from '@/components/ModelDetailView';
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

export default function Home() {
  const [gpuInfo, setGpuInfo] = useState<any>(null);
  const [diskSpace, setDiskSpace] = useState<any>(null);
  const [catalog, setCatalog] = useState<any>(null);
  const [apiKeys, setApiKeys] = useState<any>({ huggingface: '', civitai: '' });
  const [gridConfig, setGridConfig] = useState<any>({ gridApiKey: '', workerName: '', aipgWallet: '' });
  const [filter, setFilter] = useState<'all' | 'compatible' | 'installed'>('compatible');
  const [styleFilter, setStyleFilter] = useState<'all' | 'text-to-image' | 'text-to-video' | 'image-to-video' | 'image-to-image' | 'anime' | 'realistic' | 'generalist' | 'artistic' | 'video'>('all');
  const [loading, setLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState<{type: 'success' | 'error' | 'info', message: string} | null>(null);
  const [downloadStatus, setDownloadStatus] = useState<any>(null);
  const [showGettingStarted, setShowGettingStarted] = useState(false);
  const [isModelsCollapsed, setIsModelsCollapsed] = useState(false);
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

  useEffect(() => {
    loadData();
    
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
    
    // Set up SSE connection for real-time download updates
    const eventSource = new EventSource('/api/models/download/stream');
    
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
    
    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      showError('Connection Error', 'Failed to connect to download status stream. Using fallback polling.');
      
      // Fallback to polling if SSE fails
      const fallbackInterval = setInterval(async () => {
        try {
          const response = await fetch('/api/models/download/status');
          const status = await response.json();
          setDownloadStatus(status);
        } catch (error) {
          console.error('Fallback polling error:', error);
        }
      }, 3000); // Poll every 3 seconds as fallback
      
      // Clean up fallback after 5 minutes
      setTimeout(() => clearInterval(fallbackInterval), 300000);
    };
    
    return () => {
      eventSource.close();
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
  
  const loadData = async () => {
    try {
      // Load GPU info
      const gpuRes = await fetch('/api/gpu-info');
      const gpuData = await gpuRes.json();
      setGpuInfo(gpuData);

      // Load disk space
      const diskRes = await fetch('/api/disk-space');
      const diskData = await diskRes.json();
      setDiskSpace(diskData);

      // Load models catalog
      const catalogRes = await fetch('/api/models-catalog');
      const catalogData = await catalogRes.json();
      setCatalog(catalogData);

      // Load API keys
      const keysRes = await fetch('/api/api-keys');
      const keysData = await keysRes.json();
      setApiKeys(keysData);

      // Load grid config
      const gridRes = await fetch('/api/grid-config');
      const gridData = await gridRes.json();
      setGridConfig(gridData);

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
    const allCollapsed = isModelsCollapsed && isApiKeysCollapsed && isGpuInfoCollapsed && isDiskSpaceCollapsed && isGridConfigCollapsed;
    setIsModelsCollapsed(!allCollapsed);
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
          // Show countdown for rebuild
          setRestartMessage(`${modelId} is now hosted! Containers will rebuild to start earning`);
          setShowRestartCountdown(true);
        } else {
          showStatus('success', `Now hosting ${modelId}!`);
          showSuccess('Model Hosting Started', `${modelId} is already being hosted!`);
          await loadData();
        }
      } else {
        showStatus('error', 'Failed to start hosting: ' + (result.error || 'Unknown error'));
        showError('Hosting Failed', 'Failed to start hosting: ' + (result.error || 'Unknown error'));
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
      // Check if we have required API keys for this model
      const model = catalog?.models?.find((m: any) => m.id === modelId);
      
      if (!model) {
        showStatus('error', 'Model not found');
        return;
      }
      
      // Check if model has a download URL
      if (!model.config?.download_url && !model.config?.files?.[0]?.path) {
        showStatus('error', `Model ${modelId} is not downloadable - no download URL available`);
        showError('Download Not Available', `Model ${modelId} is not downloadable. This model may require manual installation or is not yet available for download.`);
        return;
      }
      
      if (model.requires_huggingface_key && !apiKeys.huggingface) {
        showStatus('error', 'HuggingFace API key required for this model. Please configure it first.');
        showError('API Key Required', 'HuggingFace API key required for this model. Please configure it first.');
        return;
      }
      
      if (model.requires_civitai_key && !apiKeys.civitai) {
        showStatus('error', 'Civitai API key required for this model. Please configure it first.');
        showError('API Key Required', 'Civitai API key required for this model. Please configure it first.');
        return;
      }
      
      showStatus('info', `Starting download of ${modelId}...`);

      // Start download - read SSE stream for progress
      const downloadRes = await fetch('/api/models/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          models: [modelId],
        }),
      });

      if (!downloadRes.ok) {
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
                  
                  if (data.type === 'complete') {
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
                    throw new Error(data.message);
                  }
                } catch (e) {
                  console.error('Error parsing SSE:', e);
                }
              }
            }
          }
        } catch (readError) {
          console.error('Error reading stream:', readError);
        }
      }
    } catch (error: any) {
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
    try {
      showStatus('info', 'Preparing to uninstall ' + modelId + '...');
      
      const res = await fetch('/api/models/uninstall', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId }),
      });
      
      const result = await res.json();
      
      if (result.success) {
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
          setPendingRestartAction(() => async () => {
            setShowRemovalDialog(false);
            setRestartMessage(`${modelId} uninstalled. Containers will rebuild`);
            setShowRestartCountdown(true);
          });
        } else if (result.requires_restart) {
          // No files removed but configuration changed, go straight to countdown
          showSuccess('Configuration Cleaned', `Removed ${modelId} from hosting configuration.`);
          setRestartMessage(`${modelId} removed from configuration. Containers will rebuild`);
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
  
  const handleRestartComplete = async () => {
    try {
      setShowRestartCountdown(false);
      setShowRebuildingPage(true);
      
      // Call the restart API with rebuild flag
      const res = await fetch('/api/containers/restart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rebuild: true }),
      });
      
      if (!res.ok) {
        const result = await res.json();
        showError('Rebuild Failed', result.error || 'Failed to rebuild containers');
        setShowRebuildingPage(false);
      }
      // If successful, the RebuildingPage component will handle the rest
    } catch (error: any) {
      showError('Rebuild Error', error.message);
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

  // Calculate API key requirements
  const modelsRequiringKeys = {
    huggingface: catalog?.models?.filter((m: any) => m.requires_huggingface_key).length || 0,
    civitai: catalog?.models?.filter((m: any) => m.requires_civitai_key).length || 0,
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
                <div>
                  <h3 className="font-semibold text-yellow-400">Download in Progress</h3>
                  <p className="text-sm text-gray-400">
                    {downloadStatus.current_model ? 
                      `Downloading ${downloadStatus.current_model}...` : 
                      'Download in progress...'
                    }
                  </p>
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
                        {downloadStatus.speed} MB/s
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
            {isModelsCollapsed && isApiKeysCollapsed && isGpuInfoCollapsed && isDiskSpaceCollapsed ? 'Expand All' : 'Collapse All'}
          </button>
        </div>

        {/* Main Content */}
        <div className="space-y-8">
          
          {/* ModelVault Status */}
          <ModelVaultStatus />

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

          {/* Main Content Area */}
          <div className="space-y-6">
            
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
            <div className="bg-gray-900 rounded-xl border border-gray-700 mt-8">
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
                    <h2 className="text-2xl font-bold text-white">API Keys Setup</h2>
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
                  <p className="text-gray-400 mb-4">
                    Some AI models require API keys to download. Don't worry - these are free to get!
                  </p>
                  <APIKeyEditor
                    huggingfaceKey={apiKeys.huggingface || ''}
                    civitaiKey={apiKeys.civitai || ''}
                    onSave={handleSaveAPIKeys}
                  />
                </div>
              </motion.div>
            </div>
            
            {/* API Key Warning */}
            <APIKeyStatus
              hasHuggingFaceKey={!!apiKeys.huggingface}
              hasCivitaiKey={!!apiKeys.civitai}
              modelsRequiringKeys={modelsRequiringKeys}
            />
            
            {/* Model Selection */}
            <div className="bg-gray-900 rounded-xl border border-gray-700">
              {/* Collapsible Header */}
              <div 
                className="flex items-center justify-between p-6 cursor-pointer hover:bg-gray-800/30 transition-colors"
                onClick={() => setIsModelsCollapsed(!isModelsCollapsed)}
              >
                <div className="flex items-center gap-3">
                  <svg className="w-6 h-6 text-aipg-orange" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                  <div>
                    <h2 className="text-2xl font-bold text-white">Choose Your AI Models</h2>
                    <p className="text-sm text-gray-400">
                      {catalog?.models ? 
                        `${catalog.models.filter((m: any) => {
                          const maxVram = gpuInfo?.gpus?.[0]?.vram_available_gb || gpuInfo?.total_memory_gb || 0;
                          return m.vram_required_gb <= maxVram;
                        }).length} models compatible (${catalog.total_count || 0} total models)` :
                        'Select AI models for your worker'
                      }
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {catalog?.installed_count > 0 && (
                    <span className="px-3 py-1 text-xs bg-blue-500/20 text-blue-400 rounded-full border border-blue-500/50">
                      {catalog.installed_count} installed
                    </span>
                  )}
                  <svg 
                    className={`w-5 h-5 text-gray-400 transition-transform ${isModelsCollapsed ? 'rotate-180' : ''}`}
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
                animate={{ height: isModelsCollapsed ? 0 : 'auto' }}
                transition={{ duration: 0.3 }}
                className="overflow-hidden"
              >
                <div className="px-6 pb-6">
                  <p className="text-gray-400 mb-6">
                    Select the AI models you want to run on your worker. Each model is specialized for different types of content creation.
                  </p>
                  
                  <ModelDetailView
                    catalog={catalog}
                    diskSpace={diskSpace}
                    filter={filter}
                    styleFilter={styleFilter}
                    gpuInfo={gpuInfo}
                    downloadStatus={downloadStatus}
                    onFilterChange={setFilter}
                    onStyleFilterChange={setStyleFilter}
                    onUninstall={handleUninstall}
                    onHost={handleHost}
                    onUnhost={handleUnhost}
                    onDownload={(modelId) => handleDownloadSingle(modelId, false)}
                    onDownloadAndHost={(modelId) => handleDownloadSingle(modelId, true)}
                    onCancelDownload={handleCancelDownload}
                    onCatalogRefresh={loadData}
                  />
                </div>
              </motion.div>
            </div>
          </div>
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
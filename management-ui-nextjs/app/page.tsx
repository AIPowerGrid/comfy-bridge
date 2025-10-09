'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import GPUInfo from '@/components/GPUInfo';
import DiskSpace from '@/components/DiskSpace';
import ModelGrid from '@/components/ModelGrid';
import Header from '@/components/Header';
import StatusMessage from '@/components/StatusMessage';
import APIKeyEditor from '@/components/APIKeyEditor';
import APIKeyStatus from '@/components/APIKeyStatus';
import GettingStartedGuide from '@/components/GettingStartedGuide';
import GridConfigEditor from '@/components/GridConfigEditor';

export default function Home() {
  const [gpuInfo, setGpuInfo] = useState<any>(null);
  const [diskSpace, setDiskSpace] = useState<any>(null);
  const [catalog, setCatalog] = useState<any>(null);
  const [apiKeys, setApiKeys] = useState<any>({ huggingface: '', civitai: '' });
  const [gridConfig, setGridConfig] = useState<any>({ gridApiKey: '', workerName: '', aipgWallet: '' });
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<'all' | 'compatible' | 'selected'>('compatible');
  const [styleFilter, setStyleFilter] = useState<'all' | 'text-to-image' | 'text-to-video' | 'image-to-video' | 'image-to-image' | 'anime' | 'realistic' | 'generalist' | 'artistic' | 'video'>('all');
  const [loading, setLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState<{type: 'success' | 'error' | 'info', message: string} | null>(null);
  const [showGettingStarted, setShowGettingStarted] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

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
      setLoading(false);
    }
  };

  const showStatus = (type: 'success' | 'error' | 'info', message: string) => {
    setStatusMessage({ type, message });
    setTimeout(() => setStatusMessage(null), 5000);
  };

  const toggleModel = (modelName: string) => {
    const newSelected = new Set(selectedModels);
    if (newSelected.has(modelName)) {
      newSelected.delete(modelName);
    } else {
      newSelected.add(modelName);
    }
    setSelectedModels(newSelected);
  };

  const handleSaveAPIKeys = async (keys: { huggingface: string; civitai: string }) => {
    try {
      const res = await fetch('/api/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(keys),
      });
      
      if (!res.ok) throw new Error('Failed to save API keys');
      
      setApiKeys(keys);
      showStatus('success', 'API keys saved successfully!');
    } catch (error: any) {
      showStatus('error', 'Failed to save API keys: ' + error.message);
      throw error;
    }
  };

  const handleSaveGridConfig = async (config: { gridApiKey: string; workerName: string; aipgWallet: string }) => {
    try {
      const res = await fetch('/api/grid-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      
      if (!res.ok) throw new Error('Failed to save grid configuration');
      
      setGridConfig(config);
      showStatus('success', 'Grid configuration saved successfully!');
    } catch (error: any) {
      showStatus('error', 'Failed to save grid configuration: ' + error.message);
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
        showStatus('success', `Now hosting ${modelId}! Restart the worker for changes to take effect.`);
        await loadData(); // Reload to update hosting status
      } else {
        showStatus('error', 'Failed to start hosting: ' + (result.error || 'Unknown error'));
      }
    } catch (error: any) {
      showStatus('error', 'Error: ' + error.message);
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
      
      if (result.success) {
        showStatus('success', `Stopped hosting ${modelId}! Restart the worker for changes to take effect.`);
        await loadData(); // Reload to update hosting status
      } else {
        showStatus('error', 'Failed to stop hosting: ' + (result.error || 'Unknown error'));
      }
    } catch (error: any) {
      showStatus('error', 'Error: ' + error.message);
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
      
      if (model.requires_huggingface_key && !apiKeys.huggingface) {
        showStatus('error', 'HuggingFace API key required for this model. Please configure it first.');
        return;
      }
      
      if (model.requires_civitai_key && !apiKeys.civitai) {
        showStatus('error', 'Civitai API key required for this model. Please configure it first.');
        return;
      }
      
      showStatus('info', `Downloading ${modelId}... This may take several minutes.`);

      // Trigger download
      const downloadRes = await fetch('/api/models/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          models: [modelId],
        }),
      });

      const result = await downloadRes.json();

      if (result.success) {
        if (autoHost) {
          showStatus('success', `${modelId} installed successfully! You're now earning money!`);
          // Automatically start hosting after download
          await handleHost(modelId);
        } else {
          showStatus('success', `${modelId} installed successfully! Click "Start Earning" to begin making money.`);
        }
        await loadData(); // Reload to update installed status
      } else {
        showStatus('error', 'Download failed: ' + (result.error || 'Unknown error'));
      }
    } catch (error: any) {
      showStatus('error', 'Error: ' + error.message);
    }
  };

  const handleSaveAndDownload = async () => {
    try {
      // Check if we have required API keys
      const selectedModelsList = Array.from(selectedModels);
      const modelsNeedingKeys = catalog?.models?.filter((m: any) => selectedModelsList.includes(m.id)) || [];
      
      const needsHF = modelsNeedingKeys.some((m: any) => m.requires_huggingface_key);
      const needsCivitai = modelsNeedingKeys.some((m: any) => m.requires_civitai_key);
      
      if (needsHF && !apiKeys.huggingface) {
        showStatus('error', 'Some models need a HuggingFace account. Get a free key above and paste it in.');
        return;
      }
      
      if (needsCivitai && !apiKeys.civitai) {
        showStatus('error', 'Some models need a Civitai account. Get a free key above and paste it in.');
        return;
      }
      
      showStatus('info', 'Starting download... This may take several minutes.');

      // Trigger download
      const downloadRes = await fetch('/api/models/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          models: selectedModelsList,
        }),
      });

      const result = await downloadRes.json();

      if (result.success) {
        showStatus('success', 'Models downloaded successfully! Your AI worker is ready.');
        await loadData(); // Reload to update installed status
      } else {
        showStatus('error', 'Download failed: ' + (result.error || 'Unknown error'));
      }
    } catch (error: any) {
      showStatus('error', 'Error: ' + error.message);
    }
  };

  const clearSelection = () => {
    setSelectedModels(new Set());
  };

  const handleUninstall = async (modelId: string) => {
    if (!confirm(`Are you sure you want to remove ${modelId}? This will delete all associated files.`)) {
      return;
    }
    
    try {
      showStatus('info', 'Removing ' + modelId + '...');
      
      const res = await fetch('/api/models/uninstall', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId }),
      });
      
      const result = await res.json();
      
      if (result.success) {
        showStatus('success', 'Model removed successfully!');
        await loadData(); // Reload to update installed status
      } else {
        showStatus('error', 'Removal failed: ' + (result.error || 'Unknown error'));
      }
    } catch (error: any) {
      showStatus('error', 'Error: ' + error.message);
    }
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

  return (
    <div className="min-h-screen bg-black text-white">
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

        {/* Main Content */}
        <div className="space-y-8">
          
          {/* System Info - Full width on mobile, sidebar on desktop */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GPUInfo gpuInfo={gpuInfo} />
            <DiskSpace diskSpace={diskSpace} />
          </div>

          {/* Main Content Area */}
          <div className="space-y-6">
            
            {/* Grid Configuration */}
            <GridConfigEditor
              gridApiKey={gridConfig.gridApiKey || ''}
              workerName={gridConfig.workerName || ''}
              aipgWallet={gridConfig.aipgWallet || ''}
              onSave={handleSaveGridConfig}
            />
            
            {/* API Keys Section */}
            <div className="bg-gray-900 rounded-xl p-6 border border-gray-700">
              <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
                <svg className="w-6 h-6 text-aipg-orange" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
                API Keys Setup
              </h2>
              <p className="text-gray-400 mb-4">
                Some AI models require API keys to download. Don't worry - these are free to get!
              </p>
              <APIKeyEditor
                huggingfaceKey={apiKeys.huggingface || ''}
                civitaiKey={apiKeys.civitai || ''}
                onSave={handleSaveAPIKeys}
              />
            </div>
            
            {/* API Key Warning */}
            <APIKeyStatus
              hasHuggingFaceKey={!!apiKeys.huggingface}
              hasCivitaiKey={!!apiKeys.civitai}
              modelsRequiringKeys={modelsRequiringKeys}
            />
            
            {/* Model Selection */}
            <div className="bg-gray-900 rounded-xl p-6 border border-gray-700">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                  <svg className="w-6 h-6 text-aipg-orange" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                  Choose Your AI Models
                </h2>
                <div className="text-sm text-gray-400">
                  <span className="font-semibold text-aipg-orange">{catalog?.total_count || 0}</span> models available
                  {catalog?.installed_count > 0 && (
                    <span className="ml-3">
                      • <span className="font-semibold text-green-400">{catalog.installed_count}</span> installed
                    </span>
                  )}
                </div>
              </div>
              
              <p className="text-gray-400 mb-6">
                Select the AI models you want to run on your worker. Each model is specialized for different types of content creation.
              </p>
              
              <ModelGrid
                catalog={catalog}
                selectedModels={selectedModels}
                diskSpace={diskSpace}
                filter={filter}
                styleFilter={styleFilter}
                gpuInfo={gpuInfo}
                onToggleModel={toggleModel}
                onFilterChange={setFilter}
                onStyleFilterChange={setStyleFilter}
                onUninstall={handleUninstall}
                onHost={handleHost}
                onUnhost={handleUnhost}
                onDownload={(modelId) => handleDownloadSingle(modelId, false)}
                onDownloadAndHost={(modelId) => handleDownloadSingle(modelId, true)}
                onSave={handleSaveAndDownload}
                onClear={clearSelection}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
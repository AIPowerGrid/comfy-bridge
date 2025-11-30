export interface FileDownloadState {
  file_name: string;
  file_type: string;
  file_size_mb: number;
  progress: number;
  speed: string;
  eta: string;
  status: 'queued' | 'downloading' | 'completed' | 'failed';
  downloaded_mb: number;
}

export interface ModelDownloadState {
  is_downloading?: boolean;
  progress: number;
  total_files: number;
  completed_files: number;
  message?: string;
  speed?: string;
  eta?: string;
  files: FileDownloadState[];
  error_message?: string;
  status?: 'pending' | 'downloading' | 'completed' | 'failed';
  processId?: number;
}

export interface DownloadProgress {
  id: string;
  modelId: string;
  status: 'pending' | 'downloading' | 'completed' | 'failed';
  progress: number; // 0-100
  message: string;
  startedAt: Date;
  completedAt?: Date;
  error?: string;
  files?: FileDownloadState[];
  processId?: number;
}

class DownloadStateManager {
  private downloads = new Map<string, DownloadProgress>();

  createDownload(modelId: string, files?: FileDownloadState[]): string {
    const id = `download_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const download: DownloadProgress = {
      id,
      modelId,
      status: 'pending',
      progress: 0,
      message: 'Initializing download...',
      startedAt: new Date(),
      files,
    };

    this.downloads.set(id, download);
    return id;
  }

  updateDownload(id: string, updates: Partial<DownloadProgress>): void {
    const download = this.downloads.get(id);
    if (download) {
      Object.assign(download, updates);
    }
  }

  getDownload(id: string): DownloadProgress | undefined {
    return this.downloads.get(id);
  }

  getAllDownloads(): DownloadProgress[] {
    return Array.from(this.downloads.values());
  }

  getDownloadsByModel(modelId: string): DownloadProgress[] {
    return Array.from(this.downloads.values()).filter(d => d.modelId === modelId);
  }

  removeDownload(id: string): void {
    this.downloads.delete(id);
  }

  clearCompletedDownloads(): void {
    for (const [id, download] of this.downloads.entries()) {
      if (download.status === 'completed' || download.status === 'failed') {
        this.downloads.delete(id);
      }
    }
  }
}

export const downloadStateManager = new DownloadStateManager();

// Additional methods for file management
export function setFileStatus(modelId: string, fileName: string, status: 'queued' | 'downloading' | 'completed' | 'failed'): void {
  const downloads = downloadStateManager.getDownloadsByModel(modelId);
  for (const download of downloads) {
    if (download.files) {
      const file = download.files.find(f => f.file_name === fileName);
      if (file) {
        file.status = status;
      }
    }
  }
}

export function updateFileProgress(
  modelId: string,
  fileName: string,
  progress: number,
  downloaded: number,
  speed: number,
  eta: string,
  totalSize: number
): void {
  const downloads = downloadStateManager.getDownloadsByModel(modelId);
  for (const download of downloads) {
    if (download.files) {
      const file = download.files.find(f => f.file_name === fileName);
      if (file) {
        file.progress = progress;
        file.downloaded_mb = downloaded;
        file.speed = `${speed} MB/s`;
        file.eta = eta;
        file.file_size_mb = totalSize;
      }
    }
  }
}

export function setProcessId(modelId: string, processId: number): void {
  const downloads = downloadStateManager.getDownloadsByModel(modelId);
  for (const download of downloads) {
    download.processId = processId;
  }
}

export function updateProgress(modelId: string, progress: number, speed?: string, eta?: string, modelIdParam?: string): void {
  const targetModelId = modelIdParam || modelId;
  const downloads = downloadStateManager.getDownloadsByModel(targetModelId);
  for (const download of downloads) {
    download.progress = progress;
    if (speed) download.message = `${speed} - ${eta || ''}`;
  }
}

export function updateDownloadMessage(modelId: string, message: string): void {
  const downloads = downloadStateManager.getDownloadsByModel(modelId);
  for (const download of downloads) {
    download.message = message;
  }
}

export function getDownloadState(modelId: string): DownloadProgress | undefined {
  const downloads = downloadStateManager.getDownloadsByModel(modelId);
  return downloads[0]; // Return the first (most recent) download for this model
}

// Helper functions for common operations
export function startDownload(modelId: string): string {
  return downloadStateManager.createDownload(modelId);
}

export function updateDownloadProgress(id: string, progress: number, message: string): void {
  downloadStateManager.updateDownload(id, { progress, message });
}

export function completeDownload(id: string): void {
  downloadStateManager.updateDownload(id, {
    status: 'completed',
    progress: 100,
    message: 'Download completed successfully',
    completedAt: new Date(),
  });
}

export function failDownload(id: string, error: string): void {
  downloadStateManager.updateDownload(id, {
    status: 'failed',
    message: `Download failed: ${error}`,
    error,
    completedAt: new Date(),
  });
}

export function getDownloadStatus(id: string): DownloadProgress | undefined {
  return downloadStateManager.getDownload(id);
}

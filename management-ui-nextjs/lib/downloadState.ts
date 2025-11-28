export interface DownloadProgress {
  id: string;
  modelId: string;
  status: 'pending' | 'downloading' | 'completed' | 'failed';
  progress: number; // 0-100
  message: string;
  startedAt: Date;
  completedAt?: Date;
  error?: string;
}

class DownloadStateManager {
  private downloads = new Map<string, DownloadProgress>();

  createDownload(modelId: string): string {
    const id = `download_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const download: DownloadProgress = {
      id,
      modelId,
      status: 'pending',
      progress: 0,
      message: 'Initializing download...',
      startedAt: new Date(),
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

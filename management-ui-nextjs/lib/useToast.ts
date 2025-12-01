import { useState, useCallback } from 'react';

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message: string;
  duration?: number;
}

type ToastInput = {
  type: Toast['type'];
  title: string;
  message?: string;
  duration?: number;
};

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((toast: ToastInput) => {
    const id = Math.random().toString(36).substring(2, 9);
    const newToast: Toast = {
      id,
      type: toast.type,
      title: toast.title,
      message: toast.message ?? '',
      duration: toast.duration ?? 5000,
    };

    setToasts((prev) => [...prev, newToast]);

    // Auto remove toast after duration
    setTimeout(() => {
      removeToast(id);
    }, newToast.duration);

    return id;
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const buildToast = useCallback((
    type: Toast['type'],
    title: string,
    detailOrDuration?: string | number,
    maybeDuration?: number
  ) => {
    let detail: string | undefined;
    let duration: number | undefined;

    if (typeof detailOrDuration === 'number') {
      duration = detailOrDuration;
    } else {
      detail = detailOrDuration;
      duration = maybeDuration;
    }

    const message = detail ?? '';
    return addToast({ type, title, message, duration });
  }, [addToast]);

  const showSuccess = useCallback((title: string, detailOrDuration?: string | number, maybeDuration?: number) => {
    return buildToast('success', title, detailOrDuration, maybeDuration);
  }, [buildToast]);

  const showError = useCallback((title: string, detailOrDuration?: string | number, maybeDuration?: number) => {
    return buildToast('error', title, detailOrDuration, maybeDuration);
  }, [buildToast]);

  const showInfo = useCallback((title: string, detailOrDuration?: string | number, maybeDuration?: number) => {
    return buildToast('info', title, detailOrDuration, maybeDuration);
  }, [buildToast]);

  const showWarning = useCallback((title: string, detailOrDuration?: string | number, maybeDuration?: number) => {
    return buildToast('warning', title, detailOrDuration, maybeDuration);
  }, [buildToast]);

  return {
    toasts,
    addToast,
    removeToast,
    showSuccess,
    showError,
    showInfo,
    showWarning,
  };
}

"use client";

/**
 * Toast — lightweight notification system.
 *
 * Provides a ToastProvider with a useToast() hook. Components call
 * showToast(message) and a small notification auto-dismisses after 3 seconds.
 */

import { createContext, useContext, useState, useCallback, ReactNode } from "react";


// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Toast {
  id: number;
  message: string;
  type: "success" | "error" | "info";
}

interface ToastContextType {
  showToast: (message: string, type?: Toast["type"]) => void;
}


// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const ToastContext = createContext<ToastContextType | null>(null);

export function useToast(): ToastContextType {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a <ToastProvider>");
  }
  return context;
}


// ---------------------------------------------------------------------------
// Provider + rendered toasts
// ---------------------------------------------------------------------------

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback(
    (message: string, type: Toast["type"] = "success") => {
      const id = nextId++;
      setToasts((prev) => [...prev, { id, message, type }]);

      // Auto-dismiss after 3 seconds
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 3000);
    },
    [],
  );

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}

      {/* Toast container — fixed bottom-right */}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`animate-slide-in-right flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium text-white shadow-lg ${
              toast.type === "success"
                ? "bg-ps-green"
                : toast.type === "error"
                  ? "bg-red-600"
                  : "bg-ps-blue"
            }`}
          >
            {/* Icon */}
            <span className="text-base">
              {toast.type === "success"
                ? "\u2713"
                : toast.type === "error"
                  ? "\u2717"
                  : "\u2139"}
            </span>
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

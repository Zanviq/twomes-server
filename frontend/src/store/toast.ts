import { create } from "zustand";

export interface Toast {
  id: number;
  msg: string;
  kind: "ok" | "error";
}

interface ToastState {
  toasts: Toast[];
  push: (msg: string, kind: "ok" | "error") => void;
  remove: (id: number) => void;
}

let nextId = 1;

export const useToast = create<ToastState>((set) => ({
  toasts: [],
  push: (msg, kind) => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts, { id, msg, kind }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 3800);
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export const toast = {
  ok: (m: string) => useToast.getState().push(m, "ok"),
  error: (m: string) => useToast.getState().push(m, "error"),
};

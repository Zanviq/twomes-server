import { Construction } from "lucide-react";
import { Shell } from "../components/layout/Shell";

export function Placeholder({ title }: { title: string }) {
  return (
    <Shell title={title}>
      <div className="flex h-[60vh] flex-col items-center justify-center gap-3 text-fg-muted">
        <Construction size={32} className="text-accent" />
        <p className="text-sm font-medium">{title} — 곧 제공됩니다</p>
      </div>
    </Shell>
  );
}

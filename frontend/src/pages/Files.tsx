import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Users, User, NotebookPen } from "lucide-react";
import { Shell } from "../components/layout/Shell";
import { FileExplorer } from "../components/files/FileExplorer";
import { Scope } from "../lib/api";
import { toast } from "../store/toast";
import { useSettings } from "../store/settings";

export function Files() {
  const defaultScope = useSettings((s) => s.settings?.files.default_scope);
  const [params] = useSearchParams();
  const urlScope = params.get("scope");
  const initialPath = params.get("path") ?? "";
  const [scope, setScope] = useState<Scope>(
    (urlScope as Scope) || (defaultScope as Scope) || "me",
  );
  return (
    <Shell
      title="파일"
      actions={
        <div className="inline-flex rounded-md border border-line bg-subtle p-0.5">
          {[
            { s: "common" as Scope, icon: Users, label: "공통" },
            { s: "me" as Scope, icon: User, label: "내 폴더" },
            { s: "notes" as Scope, icon: NotebookPen, label: "노트" },
          ].map(({ s, icon: I, label }) => (
            <button
              key={s}
              onClick={() => setScope(s)}
              className={`inline-flex items-center gap-1.5 rounded-sm px-3 py-1 text-[13px] font-medium transition-colors ${
                scope === s ? "bg-surface text-accent shadow-sm" : "text-fg-muted hover:text-fg"
              }`}
            >
              <I size={14} /> {label}
            </button>
          ))}
        </div>
      }
    >
      <FileExplorer
        key={scope}
        scope={scope}
        initialPath={scope === urlScope ? initialPath : ""}
        onError={toast.error}
        onToast={toast.ok}
      />
    </Shell>
  );
}

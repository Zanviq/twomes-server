import { Link } from "react-router-dom";
import { FolderOpen, NotebookPen, CalendarDays, Bot } from "lucide-react";
import { Shell } from "../components/layout/Shell";
import { SystemMonitor } from "../components/system/SystemMonitor";
import { useAuth } from "../store/auth";

const SHORTCUTS = [
  { to: "/files", icon: FolderOpen, label: "파일", desc: "공통·개인 파일 관리" },
  { to: "/notes", icon: NotebookPen, label: "노트", desc: "마크다운·위키링크" },
  { to: "/calendar", icon: CalendarDays, label: "캘린더", desc: "일정 관리" },
  { to: "/assistant", icon: Bot, label: "AI 비서", desc: "파일·일정 자동화" },
];

export function Dashboard() {
  const name = useAuth((s) => s.session?.display_name);
  return (
    <Shell title="대시보드">
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-bold tracking-tight">
            안녕하세요, {name}님 👋
          </h2>
          <p className="mt-0.5 text-[13px] text-fg-muted">오늘도 좋은 하루 되세요.</p>
        </div>

        <SystemMonitor />

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {SHORTCUTS.map((s) => (
            <Link
              key={s.to}
              to={s.to}
              className="card card-hover flex flex-col gap-2 p-4"
            >
              <div className="grid h-9 w-9 place-items-center rounded-md bg-accent-muted text-accent">
                <s.icon size={18} />
              </div>
              <div>
                <p className="text-sm font-semibold">{s.label}</p>
                <p className="text-[12px] text-fg-muted">{s.desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </Shell>
  );
}

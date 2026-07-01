import { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

/** 하위 트리에서 렌더 오류가 나도 흰 화면 대신 복구 UI를 보여준다. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 개발 중 콘솔 확인용
    console.error("UI 오류:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-4 bg-bg p-6 text-center">
          <div className="grid h-14 w-14 place-items-center rounded-xl bg-danger/10 text-danger">
            <AlertTriangle size={26} />
          </div>
          <div>
            <p className="text-sm font-semibold">문제가 발생했습니다</p>
            <p className="mt-1 max-w-md text-[13px] text-fg-muted">
              화면을 그리는 중 오류가 났습니다. 새로고침하면 대부분 해결됩니다.
            </p>
          </div>
          <button onClick={() => window.location.reload()} className="btn btn-primary">
            새로고침
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

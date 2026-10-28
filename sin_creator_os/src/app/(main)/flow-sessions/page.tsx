import { FlowSessionManager } from "@/components/creator/flow-session-manager";

export default function FlowSessionsPage() {
  return (
    <main className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="max-w-2xl space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">Workspace settings</p>
        <h1 className="text-2xl font-semibold tracking-tight">Flow sessions</h1>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Quản lý hồ sơ Google Flow, kiểm tra trạng thái provider và mở phiên đăng nhập được giới hạn theo workspace.
        </p>
      </header>
      <FlowSessionManager />
    </main>
  );
}

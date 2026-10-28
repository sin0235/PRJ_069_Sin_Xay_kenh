"use client";

import * as React from "react";
import Image from "next/image";
import { SidebarMenuButton } from "@/components/ui/sidebar";
import { AuthApi, type WorkspaceSession } from "@/lib/api/auth-api";

export function WorkspaceSwitcher() {
  const [workspace, setWorkspace] = React.useState<WorkspaceSession | null>(AuthApi.getCurrentWorkspace());

  React.useEffect(() => {
    void AuthApi.loadSession().then((session) => setWorkspace(session.workspace)).catch(() => setWorkspace(null));
  }, []);

  return (
    <SidebarMenuButton size="lg" className="rounded-xl border border-border/40 px-3 py-2.5">
      <div className="flex aspect-square size-8 items-center justify-center rounded-lg border border-border/80 bg-card p-0.5 shadow-sm">
        <Image src="/logo.png" alt="BAHA Logo" width={28} height={28} className="size-full object-contain" priority />
      </div>
      <div className="grid flex-1 text-left text-sm leading-tight">
        <span className="truncate font-semibold tracking-tight">{workspace?.name || AuthApi.getWorkspaceId()}</span>
        <span className="truncate text-xs text-muted-foreground">{workspace?.role || "Đang xác minh quyền"}</span>
      </div>
    </SidebarMenuButton>
  );
}

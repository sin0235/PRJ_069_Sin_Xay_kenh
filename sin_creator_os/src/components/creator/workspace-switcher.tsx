"use client";

import * as React from "react";
import Image from "next/image";
import { Check, ChevronsUpDown, Plus } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarMenuButton } from "@/components/ui/sidebar";
import { useCreatorStore } from "@/stores/use-creator-store";

const workspaces = [
  { id: "ws_01", name: "BAHA Group Creator Studio", plan: "Pro Agency", channels: 3 },
  { id: "ws_02", name: "BAHA Group Media", plan: "Enterprise", channels: 5 },
  { id: "ws_03", name: "Affiliate Test Studio", plan: "Starter", channels: 1 },
];

export function WorkspaceSwitcher() {
  const { currentWorkspace, setWorkspace } = useCreatorStore();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton
          size="lg"
          className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground rounded-xl border border-border/40 hover:border-border transition-colors px-3 py-2.5"
        >
          <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-card border border-border/80 p-0.5 shadow-sm">
            <Image
              src="/logo.png"
              alt="BAHA Logo"
              width={28}
              height={28}
              className="size-full object-contain"
              priority
            />
          </div>
          <div className="grid flex-1 text-left text-sm leading-tight">
            <span className="truncate font-semibold tracking-tight">{currentWorkspace}</span>
            <span className="truncate text-xs text-muted-foreground flex items-center gap-1.5">
              <span className="inline-block size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              TikTok Pro Workspace
            </span>
          </div>
          <ChevronsUpDown className="ml-auto size-4 text-muted-foreground" />
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="w-64 rounded-xl shadow-lg border-border/80"
        align="start"
        sideOffset={6}
      >
        <DropdownMenuLabel className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-3 py-2">
          Không Gian Làm Việc
        </DropdownMenuLabel>
        {workspaces.map((ws) => (
          <DropdownMenuItem
            key={ws.id}
            onClick={() => setWorkspace(ws.name)}
            className="flex items-center justify-between px-3 py-2 cursor-pointer rounded-lg hover:bg-muted"
          >
            <div className="flex flex-col">
              <span className="font-medium text-sm">{ws.name}</span>
              <span className="text-xs text-muted-foreground">
                {ws.plan} • {ws.channels} kênh kết nối
              </span>
            </div>
            {currentWorkspace === ws.name && <Check className="size-4 text-primary" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem className="flex items-center gap-2 px-3 py-2 text-xs text-primary font-medium cursor-pointer rounded-lg hover:bg-primary/5">
          <Plus className="size-4" />
          Thêm Workspace Mới
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

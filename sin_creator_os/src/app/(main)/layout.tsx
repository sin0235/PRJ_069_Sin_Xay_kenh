import type { ReactNode } from "react";
import { cookies, headers } from "next/headers";
import { cn } from "cn";

import { AppSidebar } from "@/app/(main)/_components/sidebar/app-sidebar";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { users } from "@/data/users";
import { getPreference } from "@/server/server-actions";

import { AccountSwitcher } from "./_components/header/account-switcher";
import { SearchDialog } from "./_components/header/search-dialog";
import { ThemeSwitcher } from "./_components/header/theme-switcher";
import { ChannelSelector } from "@/components/creator/channel-selector";
import { AIJobIndicator } from "@/components/creator/ai-job-indicator";
import { GlobalCreateButton } from "@/components/creator/global-create-button";
import { AuthGuard } from "@/components/auth/auth-guard";

export default async function MainLayout({ children }: Readonly<{ children: ReactNode }>) {
  const cookieStore = await cookies();
  const requestHeaders = await headers();
  const devAuthBypass = requestHeaders.get("x-sin-dev-auth-bypass") === "1";
  const defaultOpen = cookieStore.get("sidebar_state")?.value !== "false";
  const [variant, collapsible] = await Promise.all([
    getPreference("sidebar_variant"),
    getPreference("sidebar_collapsible"),
  ]);

  return (
    <AuthGuard devAuthBypass={devAuthBypass}>
      <SidebarProvider
        defaultOpen={defaultOpen}
        style={
          {
            "--sidebar-width": "calc(var(--spacing) * 66)",
          } as React.CSSProperties
        }
      >
        <AppSidebar variant={variant} collapsible={collapsible} />
        <SidebarInset
          className={cn(
            "peer-data-[variant=inset]:border",
            "[--dashboard-header-height:--spacing(12)]",
            "min-w-0 overflow-x-clip bg-background flex flex-col flex-1",
          )}
        >
          <header
            className={cn(
              "flex h-12 shrink-0 items-center border-b border-border/80 px-4 transition-[width,height] ease-linear bg-background/80 backdrop-blur-md sticky top-0 z-40",
            )}
          >
            <div className="flex w-full items-center justify-between gap-2">
              {/* Left: Sidebar trigger & Search & Channel */}
              <div className="flex items-center gap-2">
                <SidebarTrigger className="-ml-1 text-muted-foreground hover:text-foreground" />
                <Separator orientation="vertical" className="h-4 data-[orientation=vertical]:self-center" />
                <SearchDialog />
              </div>

              {/* Right: Channel Switcher, AI Jobs, Global Create, Theme, Account */}
              <div className="flex items-center gap-2">
                <ChannelSelector />
                <AIJobIndicator />
                <GlobalCreateButton />
                <Separator orientation="vertical" className="h-4 data-[orientation=vertical]:self-center hidden sm:block" />
                <ThemeSwitcher />
                <AccountSwitcher users={users} />
              </div>
            </div>
          </header>

          {/* Workspace Canvas Body */}
          <main className="min-h-0 min-w-0 flex-1 overflow-x-hidden p-4 md:p-6">
            {children}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </AuthGuard>
  );
}

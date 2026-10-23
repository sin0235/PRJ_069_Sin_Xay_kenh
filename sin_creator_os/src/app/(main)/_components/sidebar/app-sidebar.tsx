"use client";

import * as React from "react";
import { useShallow } from "zustand/react/shallow";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar";
import { sidebarItems } from "@/navigation/sidebar/sidebar-items";
import { usePreferencesStore } from "@/stores/preferences/preferences-provider";
import { WorkspaceSwitcher } from "@/components/creator/workspace-switcher";
import { AuthApi } from "@/lib/api/auth-api";

import { NavMain } from "./nav-main";
import { NavUser } from "./nav-user";

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { sidebarVariant, sidebarCollapsible, isSynced } = usePreferencesStore(
    useShallow((s) => ({
      sidebarVariant: s.values.sidebar_variant,
      sidebarCollapsible: s.values.sidebar_collapsible,
      isSynced: s.isSynced,
    })),
  );

  const [currentUser, setCurrentUser] = React.useState({
    name: "Sin Admin",
    email: "sin@test.com",
    avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80",
    role: "WORKSPACE_OWNER",
  });

  React.useEffect(() => {
    const user = AuthApi.getCurrentUser();
    if (user) {
      setCurrentUser({
        name: user.full_name || "Sin Admin",
        email: user.email || "sin@test.com",
        avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80",
        role: user.role || "WORKSPACE_OWNER",
      });
    }
  }, []);

  const variant = isSynced ? sidebarVariant : props.variant;
  const collapsible = isSynced ? sidebarCollapsible : props.collapsible;

  return (
    <Sidebar {...props} variant={variant} collapsible={collapsible} className="border-r border-border/80">
      <SidebarHeader className="p-3">
        <WorkspaceSwitcher />
      </SidebarHeader>

      <SidebarContent className="px-2">
        <NavMain items={sidebarItems} />
      </SidebarContent>

      <SidebarFooter className="p-3 border-t border-border/60">
        <NavUser user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  );
}

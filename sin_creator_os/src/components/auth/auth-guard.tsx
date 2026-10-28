"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { AuthApi } from "@/lib/api/auth-api";
import { ShieldAlert, Loader2 } from "lucide-react";

export function AuthGuard({ children, devAuthBypass = false }: { children: React.ReactNode; devAuthBypass?: boolean }) {
  const pathname = usePathname();
  const isAuthPage = pathname.startsWith("/auth/");
  const [isChecking, setIsChecking] = React.useState(!devAuthBypass && !isAuthPage);
  const [authorized, setAuthorized] = React.useState(devAuthBypass || isAuthPage);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (devAuthBypass) {
      setAuthorized(true);
      setIsChecking(false);
      return;
    }

    // Không áp dụng guard cho các trang đăng nhập/đăng ký
    if (pathname.startsWith("/auth/")) {
      setAuthorized(true);
      setIsChecking(false);
      return;
    }

    let cancelled = false;
    void AuthApi.loadSession().then((session) => {
      if (!cancelled && session) {
        setAuthorized(true);
      }
    }).catch((reason: unknown) => {
      if (!cancelled) {
        setError(reason instanceof Error ? reason.message : "Không xác minh được phiên Cloudflare Access.");
      }
    }).finally(() => {
      setIsChecking(false);
    });
    return () => { cancelled = true; };
  }, [devAuthBypass, pathname]);

  if (isChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3 text-center">
          <Loader2 className="size-8 animate-spin text-primary" />
          <p className="text-sm font-medium text-muted-foreground">Đang xác minh quyền truy cập hệ thống...</p>
        </div>
      </div>
    );
  }

  if (!authorized && !pathname.startsWith("/auth/")) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <div className="flex max-w-sm flex-col items-center gap-3 text-center p-6 border rounded-2xl bg-card shadow-sm">
          <div className="size-12 rounded-full bg-destructive/10 flex items-center justify-center text-destructive">
            <ShieldAlert className="size-6" />
          </div>
          <h2 className="text-base font-bold text-foreground">Yêu Cầu Xác Thực Danh Tính</h2>
          <p className="text-xs text-muted-foreground">
            {error || "Tài khoản chưa được cấp quyền truy cập SIN Creator OS. Hãy kiểm tra chính sách Cloudflare Access và quyền workspace."}
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

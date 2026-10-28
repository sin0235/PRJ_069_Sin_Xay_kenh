"use client";

import * as React from "react";

import { usePathname, useRouter } from "next/navigation";

import { Loader2, ShieldAlert } from "lucide-react";

import { AuthApi } from "@/lib/api/auth-api";

export function AuthGuard({ children, devAuthBypass = false }: { children: React.ReactNode; devAuthBypass?: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const [check, setCheck] = React.useState<{ pathname: string; authorized: boolean } | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    if (devAuthBypass) {
      setCheck({ pathname, authorized: true });
      return () => {
        cancelled = true;
      };
    }

    if (pathname.startsWith("/auth/")) {
      setCheck({ pathname, authorized: true });
      return () => {
        cancelled = true;
      };
    }

    setCheck(null);
    void AuthApi.refreshSession().then((session) => {
      if (cancelled) return;
      const authorized = Boolean(session);
      setCheck({ pathname, authorized });
      if (!authorized) {
        router.replace(`/auth/v1/login?redirect=${encodeURIComponent(pathname)}`);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [devAuthBypass, pathname, router]);

  const currentCheck = check?.pathname === pathname ? check : null;
  if (!currentCheck) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3 text-center">
          <Loader2 className="size-8 animate-spin text-primary" />
          <p className="text-sm font-medium text-muted-foreground">Đang xác minh quyền truy cập hệ thống...</p>
        </div>
      </div>
    );
  }

  if (!currentCheck.authorized && !pathname.startsWith("/auth/")) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <div className="flex max-w-sm flex-col items-center gap-3 text-center p-6 border rounded-2xl bg-card shadow-sm">
          <div className="size-12 rounded-full bg-destructive/10 flex items-center justify-center text-destructive">
            <ShieldAlert className="size-6" />
          </div>
          <h2 className="text-base font-bold text-foreground">Yêu Cầu Xác Thực Danh Tính</h2>
          <p className="text-xs text-muted-foreground">
            Bạn chưa đăng nhập vào hệ thống SIN Creator OS. Đang chuyển hướng bạn đến màn hình đăng nhập...
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

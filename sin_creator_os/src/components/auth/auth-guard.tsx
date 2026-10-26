"use client";

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
import { AuthApi } from "@/lib/api/auth-api";
import { ShieldAlert, Loader2 } from "lucide-react";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isChecking, setIsChecking] = React.useState(true);
  const [authorized, setAuthorized] = React.useState(false);

  React.useEffect(() => {
    if (process.env.NODE_ENV === "development") return;

    // Không áp dụng guard cho các trang đăng nhập/đăng ký
    if (pathname.startsWith("/auth/")) {
      setAuthorized(true);
      setIsChecking(false);
      return;
    }

    let isAuthed = false;
    try {
      isAuthed = AuthApi.isAuthenticated();
    } catch {
      isAuthed = false;
    }
    if (!isAuthed) {
      setAuthorized(false);
      setIsChecking(false);
      router.replace(`/auth/v1/login?redirect=${encodeURIComponent(pathname)}`);
    } else {
      setAuthorized(true);
      setIsChecking(false);
    }
  }, [pathname, router]);

  if (process.env.NODE_ENV === "development") return <>{children}</>;

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
            Bạn chưa đăng nhập vào hệ thống SIN Creator OS. Đang chuyển hướng bạn đến màn hình đăng nhập...
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

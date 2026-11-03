import type { Metadata } from "next";
import Image from "next/image";
import { APP_CONFIG } from "@/config/app-config";
import { LoginForm } from "../../_components/login-form";

export const metadata: Metadata = {
  title: `Đăng Nhập | ${APP_CONFIG.fullName}`,
  description: APP_CONFIG.tagline,
};

export default function LoginV1() {
  return (
    <div className="flex min-h-screen w-full items-center justify-center p-4 sm:p-6 md:p-8 bg-muted/20">
      <div className="w-full max-w-[420px] space-y-6">
        {/* Brand Header */}
        <div className="flex flex-col items-center text-center space-y-3">
          <div className="relative flex size-16 items-center justify-center rounded-2xl bg-card p-2 border border-border/80 shadow-md">
            <Image
              src="/logo.png"
              alt="BAHA Creator Studio Logo"
              width={64}
              height={64}
              className="size-full object-contain"
              priority
            />
          </div>
          <div className="space-y-1">
            <h1 className="text-xl font-bold tracking-tight text-foreground">
              {APP_CONFIG.fullName}
            </h1>
            <p className="text-xs text-muted-foreground">
              Nhập thông tin tài khoản của bạn để tiếp tục
            </p>
          </div>
        </div>

        {/* Card Form đăng nhập chuẩn theme hệ thống */}
        <div className="rounded-2xl border border-border/80 bg-card p-6 sm:p-8 shadow-sm">
          <LoginForm />
        </div>

        {/* Footer bản quyền thanh lịch */}
        <p className="text-center text-[11px] text-muted-foreground select-none">
          {APP_CONFIG.copyright}
        </p>
      </div>
    </div>
  );
}

"use client";

import * as React from "react";

import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, Loader2, Lock, LogIn, Mail } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { AuthApi } from "@/lib/api/auth-api";

const localPasswordMode = true;

export function LoginForm() {
  const [targetUrl, setTargetUrl] = React.useState("/dashboard");
  const [loading, setLoading] = React.useState(false);
  const [showPassword, setShowPassword] = React.useState(false);
  const [alreadyAuthed, setAlreadyAuthed] = React.useState(false);
  const [checkingSession, setCheckingSession] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    async function initialize() {
      const session = await AuthApi.refreshSession();
      if (cancelled) return;
      if (session) {
        setAlreadyAuthed(true);
        window.location.replace("/dashboard");
        return;
      }

      // 2. Phân tích tham số redirect
      const params = new URLSearchParams(window.location.search);
      const redirect = params.get("redirect");
      if (redirect && !redirect.startsWith("/auth") && redirect !== "/") {
        setTargetUrl(redirect);
      }
      setCheckingSession(false);
    }

    void initialize();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleLogin(e?: React.FormEvent | React.MouseEvent) {
    if (e?.preventDefault) e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const res = await AuthApi.login(data.email, data.password);
      if (res.success) {
        toast.success("Đăng nhập thành công!", {
          description: "Đang tự động chuyển hướng vào không gian làm việc...",
        });

        const destination = targetUrl && targetUrl !== "/" && !targetUrl.startsWith("/auth") ? targetUrl : "/dashboard";

        // Tự động chuyển hướng ngay lập tức (Hard Redirect qua window.location.replace)
        setTimeout(() => {
          window.location.replace(destination);
        }, 150);
      } else {
        toast.error("Đăng nhập thất bại", {
          description: res.error ?? "Email hoặc mật khẩu không chính xác. Vui lòng kiểm tra lại.",
        });
        setLoading(false);
      }
      setError(reason instanceof Error ? reason.message : "Không đăng nhập được.");
    } finally {
      setSubmitting(false);
    }
  }

  if (checkingSession || alreadyAuthed) {
    return (
      <div className="flex flex-col items-center justify-center p-8 gap-3 text-center">
        <Loader2 className="size-6 animate-spin text-primary" />
        <p className="text-sm font-medium text-foreground">
          {alreadyAuthed ? "Bạn đã đăng nhập. Đang chuyển vào hệ thống..." : "Đang xác minh phiên đăng nhập..."}
        </p>
      </div>
    );
  }

  return (
    <form noValidate onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-5">
      <FieldGroup className="gap-4">
        {/* Email Field */}
        <Controller
          control={form.control}
          name="email"
          render={({ field, fieldState }) => (
            <Field className="gap-1.5" data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="login-email" className="text-xs font-semibold text-foreground">
                Email
              </FieldLabel>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
                <Input
                  {...field}
                  id="login-email"
                  type="email"
                  placeholder="name@company.com"
                  autoComplete="email"
                  className="pl-9 h-10 text-sm rounded-xl border-border/80 bg-background/60 focus:bg-background transition-all"
                  aria-invalid={fieldState.invalid}
                  disabled={loading}
                />
              </div>
              {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
            </Field>
          )}
        />

        {/* Password Field */}
        <Controller
          control={form.control}
          name="password"
          render={({ field, fieldState }) => (
            <Field className="gap-1.5" data-invalid={fieldState.invalid}>
              <div className="flex items-center justify-between">
                <FieldLabel htmlFor="login-password" className="text-xs font-semibold text-foreground">
                  Mật khẩu
                </FieldLabel>
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
                <Input
                  {...field}
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  className="pl-9 pr-10 h-10 text-sm rounded-xl border-border/80 bg-background/60 focus:bg-background transition-all"
                  aria-invalid={fieldState.invalid}
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus:outline-hidden transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
            </Field>
          )}
        />

        {/* Remember me Checkbox */}
        <Controller
          control={form.control}
          name="remember"
          render={({ field, fieldState }) => (
            <Field
              orientation="horizontal"
              className="items-center justify-between pt-1"
              data-invalid={fieldState.invalid}
            >
              <div className="flex items-center gap-2">
                <Checkbox
                  id="login-remember"
                  name={field.name}
                  checked={field.value}
                  onCheckedChange={(checked) => field.onChange(Boolean(checked))}
                  aria-invalid={fieldState.invalid}
                  disabled={loading}
                  className="rounded-md"
                />
                <FieldLabel
                  htmlFor="login-remember"
                  className="font-normal text-xs text-muted-foreground cursor-pointer select-none"
                >
                  Ghi nhớ phiên đăng nhập
                </FieldLabel>
              </div>
            </Field>
          )}
        />
      </FieldGroup>

      {/* Submit Button */}
      <Button
        className="w-full h-10 text-sm font-semibold rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground shadow-md transition-all mt-1"
        type="submit"
        disabled={loading}
      >
        {loading ? (
          <span className="flex items-center gap-2">
            <Loader2 className="size-4 animate-spin" />
            Đang đăng nhập...
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <LogIn className="size-4" />
            Đăng Nhập
          </span>
        )}
      </Button>
    </form>
  );
}

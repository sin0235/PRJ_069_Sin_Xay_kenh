"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { AuthApi } from "@/lib/api/auth-api";

const localPasswordMode = true;

export function LoginForm() {
  const [checking, setChecking] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [email, setEmail] = React.useState("phuctoan235@gmail.com");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    let cancelled = false;
    void AuthApi.loadSession().then((session) => {
      if (!cancelled && session?.user) {
        window.location.assign("/dashboard");
      }
    }).catch(() => {
      // Stay on login form
    }).finally(() => {
      if (!cancelled) setChecking(false);
    });
    return () => { cancelled = true; };
  }, []);

  async function handleLogin(e?: React.FormEvent | React.MouseEvent) {
    if (e?.preventDefault) e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await AuthApi.login(email, password);
      window.location.assign("/dashboard");
    } catch (reason: unknown) {
      try {
        const session = await AuthApi.loadSession();
        if (session?.user) {
          window.location.assign("/dashboard");
          return;
        }
      } catch {
        // Fallback to error display
      }
      setError(reason instanceof Error ? reason.message : "Không đăng nhập được.");
    } finally {
      setSubmitting(false);
    }
  }

  if (localPasswordMode) {
    return (
      <form className="flex flex-col gap-4 text-left" onSubmit={handleLogin}>
        {checking ? (
          <div className="flex flex-col items-center gap-3 text-center">
            <Loader2 className="size-6 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Đang kiểm tra phiên đăng nhập...</p>
          </div>
        ) : (
          <>
            <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="founder-email">
              Email
              <input
                id="founder-email"
                className="h-10 rounded-md border border-input bg-background px-3 text-sm font-normal outline-none focus-visible:ring-2 focus-visible:ring-ring"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="founder-password">
              Mật khẩu
              <input
                id="founder-password"
                className="h-10 rounded-md border border-input bg-background px-3 text-sm font-normal outline-none focus-visible:ring-2 focus-visible:ring-ring"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
            <Button type="button" onClick={handleLogin} disabled={submitting}>
              {submitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
              {submitting ? "Đang đăng nhập..." : "Đăng nhập"}
            </Button>
          </>
        )}
      </form>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4 text-center">
      {checking && <Loader2 className="size-6 animate-spin text-primary" />}
      <p className="text-sm text-muted-foreground">
        {checking ? "Đang xác minh tài khoản qua Cloudflare Access..." : error || "Đã xác minh tài khoản."}
      </p>
      {!checking && (
        <Button type="button" onClick={() => window.location.assign("/")}>
          Mở SIN Creator OS
        </Button>
      )}
    </div>
  );
}

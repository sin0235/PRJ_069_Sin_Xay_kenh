// Client Service giao tiếp với Authentication API (PRJ_069)
// Bắt buộc xác thực tài khoản thực quyền cao nhất sin@test.com / 121232

export const DEFAULT_DEV_TOKEN =
  "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJzdWIiOiAidXNyX3Npbl9vd25lciIsICJpc3MiOiAiYmFoYS1hdXRoLWlzc3VlciIsICJhdWQiOiAic2luLWNvbnRlbnQtdGVzdCIsICJleHAiOiAxODkzNDU2MDAwLCAid29ya3NwYWNlX2lkIjogImRlZmF1bHRfd3MiLCAiZW1haWwiOiAic2luQHRlc3QuY29tIiwgIm5hbWUiOiAiU2luIEFkbWluIChIaWdoZXN0IFByaXZpbGVnZSkiLCAicm9sZSI6ICJQTEFURk9STV9PV05FUiJ9.4z6KRyymGYvOGltsTehDvG-rVMl_ggr6WTpmzby0Gzk";

export interface UserSession {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

export interface WorkspaceSession {
  id: string;
  name: string;
}

export interface LoginResult {
  success: boolean;
  token?: string;
  user?: UserSession;
  workspace?: WorkspaceSession;
  error?: string;
}

export class AuthApi {
  static isAuthenticated(): boolean {
    if (typeof window === "undefined") return false;
    const token = localStorage.getItem("baha_auth_token") || localStorage.getItem("baha_access_token");
    if (token && token.length > 20) return true;
    const hasCookie = document.cookie.split(";").some((item) => item.trim().startsWith("baha_auth_token="));
    return Boolean(hasCookie);
  }

  static getAuthToken(): string {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("baha_auth_token") || localStorage.getItem("baha_access_token");
      if (stored && stored.length > 20) return stored;
      // Trích xuất từ cookie nếu localStorage bị trống
      const match = document.cookie.match(/baha_auth_token=([^;]+)/);
      if (match && match[1]) return decodeURIComponent(match[1]);
    }
    return DEFAULT_DEV_TOKEN;
  }

  static getWorkspaceId(): string {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("baha_workspace_id");
      if (stored) return stored;
    }
    return "default_ws";
  }

  static getCurrentUser(): UserSession {
    if (typeof window !== "undefined") {
      const raw = localStorage.getItem("baha_user_profile");
      if (raw) {
        try {
          return JSON.parse(raw);
        } catch {
          // ignore
        }
      }
    }
    return {
      id: "usr_sin_owner",
      email: "sin@test.com",
      full_name: "Sin Admin (Highest Privilege)",
      role: "WORKSPACE_OWNER",
    };
  }

  static getAuthHeaders(): Record<string, string> {
    const token = this.getAuthToken() || DEFAULT_DEV_TOKEN;
    const headers: Record<string, string> = {
      "X-Workspace-Id": this.getWorkspaceId(),
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
    };
    return headers;
  }

  static async login(email: string, pass: string): Promise<LoginResult> {
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password: pass }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        return {
          success: false,
          error: data.error || "Email hoặc mật khẩu không chính xác.",
        };
      }

      if (typeof window !== "undefined") {
        localStorage.setItem("baha_auth_token", data.token);
        localStorage.setItem("baha_access_token", data.token);
        localStorage.setItem("baha_workspace_id", data.workspace?.id || "default_ws");
        localStorage.setItem("baha_user_profile", JSON.stringify(data.user));

        document.cookie = `baha_auth_token=${encodeURIComponent(data.token)}; path=/; max-age=2592000; SameSite=Lax`;
      }

      return {
        success: true,
        token: data.token,
        user: data.user,
        workspace: data.workspace,
      };
    } catch (e: any) {
      return { success: false, error: e?.message || "Không thể kết nối đến máy chủ xác thực." };
    }
  }

  static async logout(): Promise<void> {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      // ignore
    }

    if (typeof window !== "undefined") {
      localStorage.removeItem("baha_auth_token");
      localStorage.removeItem("baha_access_token");
      localStorage.removeItem("baha_workspace_id");
      localStorage.removeItem("baha_user_profile");
      document.cookie = "baha_auth_token=; path=/; max-age=0; SameSite=Lax";
    }
  }
}

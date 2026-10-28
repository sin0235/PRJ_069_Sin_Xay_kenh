// Client Service giao tiếp với Authentication API (PRJ_069)
function browserStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage || null;
  } catch {
    return null;
  }
}

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
    const storage = browserStorage();
    const token = storage?.getItem("baha_auth_token") || storage?.getItem("baha_access_token");
    if (token && token.length > 20) return true;
    try {
      return document.cookie.split(";").some((item) => item.trim().startsWith("baha_auth_token="));
    } catch {
      return false;
    }
  }

  static getAuthToken(): string {
    if (typeof window !== "undefined") {
      const storage = browserStorage();
      const stored = storage?.getItem("baha_auth_token") || storage?.getItem("baha_access_token");
      if (stored && stored.length > 20) return stored;
      // Trích xuất từ cookie nếu localStorage bị trống
      try {
        const match = document.cookie.match(/baha_auth_token=([^;]+)/);
        if (match && match[1]) return decodeURIComponent(match[1]);
      } catch {
        return "";
      }
    }
    return "";
  }

  static getWorkspaceId(): string {
    if (typeof window !== "undefined") {
      const stored = browserStorage()?.getItem("baha_workspace_id");
      if (stored) return stored;
    }
    return "default_ws";
  }

  static getCurrentUser(): UserSession {
    if (typeof window !== "undefined") {
      const raw = browserStorage()?.getItem("baha_user_profile");
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
    const token = this.getAuthToken();
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
        const storage = browserStorage();
        storage?.setItem("baha_auth_token", data.token);
        storage?.setItem("baha_access_token", data.token);
        storage?.setItem("baha_workspace_id", data.workspace?.id || "default_ws");
        storage?.setItem("baha_user_profile", JSON.stringify(data.user));

        try {
          document.cookie = `baha_auth_token=${encodeURIComponent(data.token)}; path=/; max-age=2592000; SameSite=Lax`;
        } catch {
          // Cookie HTTP-only từ route đăng nhập vẫn được giữ.
        }
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
      const storage = browserStorage();
      storage?.removeItem("baha_auth_token");
      storage?.removeItem("baha_access_token");
      storage?.removeItem("baha_workspace_id");
      storage?.removeItem("baha_user_profile");
      try {
        document.cookie = "baha_auth_token=; path=/; max-age=0; SameSite=Lax";
      } catch {
        // Cookie đã được xóa qua route logout.
      }
    }
  }
}

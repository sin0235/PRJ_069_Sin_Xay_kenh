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

export interface AuthSession {
  user: UserSession;
  workspace: WorkspaceSession;
}

export interface LoginResult {
  success: boolean;
  token?: string;
  user?: UserSession;
  workspace?: WorkspaceSession;
  error?: string;
}

let currentUser: UserSession | null = null;
let currentWorkspace: WorkspaceSession | null = null;

function clearStoredSession(): void {
  currentUser = null;
  currentWorkspace = null;
  const storage = browserStorage();
  try {
    storage?.removeItem("baha_workspace_id");
    storage?.removeItem("baha_user_profile");
  } catch {
    // Browser storage is only a display cache; cookie validation remains authoritative.
  }
}

export class AuthApi {
  static isAuthenticated(): boolean {
    return Boolean(currentUser?.id && currentWorkspace?.id);
  }

  static getAuthToken(): string {
    return "";
  }

  static getWorkspaceId(): string {
    if (currentWorkspace?.id) return currentWorkspace.id;
    try {
      return browserStorage()?.getItem("baha_workspace_id") || "";
    } catch {
      return "";
    }
  }

  static getCurrentUser(): UserSession {
    if (currentUser) return currentUser;
    try {
      const raw = browserStorage()?.getItem("baha_user_profile");
      if (raw) {
        currentUser = JSON.parse(raw) as UserSession;
        return currentUser;
      }
    } catch {
      // Invalid local profile is ignored; the server cookie remains authoritative.
    }
    return { id: "", email: "", full_name: "", role: "" };
  }

  static getAuthHeaders(): Record<string, string> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const workspaceId = AuthApi.getWorkspaceId();
    if (workspaceId) headers["X-Workspace-Id"] = workspaceId;
    return headers;
  }

  static async refreshSession(): Promise<AuthSession | null> {
    const storage = browserStorage();

    const workspaceId = AuthApi.getWorkspaceId();
    const headers: Record<string, string> = {};
    if (workspaceId) headers["X-Workspace-Id"] = workspaceId;

    try {
      const response = await fetch("/v1/auth/me", {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers,
      });
      if (!response.ok) {
        clearStoredSession();
        return null;
      }

      const data = await response.json();
      if (
        !data.user?.id ||
        !data.user?.email ||
        !data.workspace?.id ||
        !data.workspace?.name ||
        (data.workspace_id && data.workspace_id !== data.workspace.id) ||
        (workspaceId && workspaceId !== data.workspace.id)
      ) {
        clearStoredSession();
        return null;
      }

      const session: AuthSession = {
        user: {
          id: data.user.id,
          email: data.user.email,
          full_name: data.user.full_name || data.user.email,
          role: typeof data.user.role === "string" ? data.user.role : "",
        },
        workspace: {
          id: data.workspace.id,
          name: data.workspace.name,
        },
      };
      currentUser = session.user;
      currentWorkspace = session.workspace;
      try {
        storage?.setItem("baha_workspace_id", session.workspace.id);
        storage?.setItem("baha_user_profile", JSON.stringify(session.user));
      } catch {
        // In-memory state still lets mounted UI render the verified profile.
      }
      return session;
    } catch {
      clearStoredSession();
      return null;
    }
  }

  static async login(email: string, pass: string): Promise<LoginResult> {
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password: pass }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        return { success: false, error: data.error || "Email hoặc mật khẩu không chính xác." };
      }
      if (!data.user?.id || !data.workspace?.id) {
        return { success: false, error: "Máy chủ xác thực trả về hồ sơ không hợp lệ." };
      }

      const storage = browserStorage();
      currentUser = data.user;
      currentWorkspace = data.workspace;
      try {
        storage?.setItem("baha_workspace_id", data.workspace.id);
        storage?.setItem("baha_user_profile", JSON.stringify(data.user));
      } catch {
        // The HttpOnly cookie remains the session source of truth.
      }

      return { success: true, user: data.user, workspace: data.workspace };
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Không thể kết nối đến máy chủ xác thực.";
      return { success: false, error: message };
    }
  }

  static async logout(): Promise<void> {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
    } catch {
      // Clear the local display state even if the server is unavailable.
    }

    clearStoredSession();
  }
}

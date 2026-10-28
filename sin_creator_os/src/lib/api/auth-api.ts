export interface UserSession {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

export interface WorkspaceSession {
  id: string;
  name: string;
  role: string;
}

interface AuthSession {
  user: Omit<UserSession, "role">;
  workspace: WorkspaceSession;
  workspaces: WorkspaceSession[];
}

export class AuthApi {
  private static session: AuthSession | null = null;

  static async login(email: string, password: string): Promise<void> {
    const response = await fetch("/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ email, password }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: string };
      throw new Error(body.detail || "Không đăng nhập được.");
    }
    this.session = null;
    await this.loadSession();
  }

  static async loadSession(): Promise<AuthSession> {
    if (this.session) return this.session;
    const response = await fetch("/v1/auth/me", { cache: "no-store", credentials: "same-origin" });
    if (!response.ok) throw new Error(response.status === 403 ? "Tài khoản chưa được cấp quyền trong workspace." : process.env.NEXT_PUBLIC_AUTH_MODE === "local_password" ? "Chưa đăng nhập vào SIN Creator OS." : "Chưa xác minh được phiên Cloudflare Access.");
    this.session = await response.json() as AuthSession;
    return this.session;
  }

  static isAuthenticated(): boolean {
    return this.session !== null;
  }

  static getWorkspaceId(): string {
    return this.session?.workspace.id || "b6102190-1f6f-5624-bfb8-2e1091fa2560";
  }

  static getCurrentWorkspace(): WorkspaceSession | null {
    return this.session?.workspace || null;
  }

  static getCurrentUser(): UserSession | null {
    return this.session ? { ...this.session.user, role: this.session.workspace.role } : null;
  }

  static getAuthHeaders(): Record<string, string> {
    return {
      "X-Workspace-Id": this.getWorkspaceId(),
      "Content-Type": "application/json",
    };
  }

  static async logout(): Promise<void> {
    this.session = null;
    if (typeof window !== "undefined") {
      if (process.env.NEXT_PUBLIC_AUTH_MODE === "local_password") {
        await fetch("/v1/auth/logout", { method: "POST", credentials: "same-origin" });
        window.location.assign("/auth/v1/login");
      } else {
        window.location.assign("/cdn-cgi/access/logout");
      }
    }
  }
}

"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { AlertCircle, Check, Loader2, LogIn, MonitorUp, Plus, RefreshCw, X } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  flowSessionApi,
  type FlowLoginSession,
  type FlowLoginSessionState,
  type FlowProfile,
  type FlowProviderState,
  FlowSessionApiError,
} from "@/lib/api/flow-session-api";

export interface FlowSessionManagerProps {
  onProfileChange?: (profileId: string | null) => void;
}

const terminalSessionStates = new Set<FlowLoginSessionState>(["CLOSED", "TIMED_OUT", "FAILED", "INTERRUPTED"]);
const sessionLabels: Record<FlowLoginSessionState, string> = {
  LOGIN_REQUESTED: "Đang chờ tài nguyên video",
  OPENING: "Đang mở desktop riêng",
  OPEN: "Desktop đang mở",
  CLOSE_REQUESTED: "Đang đóng desktop",
  CLOSED: "Đã đóng",
  TIMED_OUT: "Phiên đăng nhập đã hết hạn",
  FAILED: "Không thể mở phiên đăng nhập",
  INTERRUPTED: "Phiên bị gián đoạn",
};

const providerLabels: Record<FlowProviderState, string> = {
  READY: "Sẵn sàng",
  LOGIN_REQUIRED: "Cần đăng nhập",
  QUOTA_LIMITED: "Đã hết hạn mức",
  UNKNOWN: "Chưa kiểm tra",
  CHECK_FAILED: "Kiểm tra thất bại",
};

function readableError(error: unknown): { message: string; code?: string } {
  if (error instanceof FlowSessionApiError) return { message: error.message, code: error.errorCode };
  if (error instanceof Error) return { message: error.message };
  return { message: "Không thể kết nối dịch vụ Flow. Hãy thử lại." };
}

function stateVariant(state: FlowProviderState): "secondary" | "destructive" | "outline" {
  if (state === "READY") return "secondary";
  if (state === "QUOTA_LIMITED" || state === "CHECK_FAILED") return "destructive";
  return "outline";
}

function ProviderState({ label, state }: { label: string; state: FlowProviderState }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 rounded-lg border border-border/70 px-3 py-2">
      <span className="truncate text-sm text-muted-foreground">{label}</span>
      <Badge variant={stateVariant(state)} className="shrink-0">{providerLabels[state]}</Badge>
    </div>
  );
}

export function FlowSessionManager({ onProfileChange }: FlowSessionManagerProps) {
  const [profiles, setProfiles] = useState<FlowProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [loginSession, setLoginSession] = useState<FlowLoginSession | null>(null);
  const [desktopUrl, setDesktopUrl] = useState<string | null>(null);
  const [desktopKey, setDesktopKey] = useState(0);
  const [newName, setNewName] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<"create" | "activate" | "check" | "login" | "close" | "desktop" | null>(null);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);
  const [notice, setNotice] = useState("");
  const selectedProfileRef = useRef<string | null>(null);
  const onProfileChangeRef = useRef(onProfileChange);

  useEffect(() => {
    onProfileChangeRef.current = onProfileChange;
  }, [onProfileChange]);

  const notifyProfileChange = useCallback((profileId: string | null) => {
    selectedProfileRef.current = profileId;
    setSelectedProfileId(profileId);
    onProfileChangeRef.current?.(profileId);
  }, []);

  const refreshProfiles = useCallback(async (preferredId?: string | null) => {
    const rows = await flowSessionApi.listProfiles();
    setProfiles(rows);
    const preferred = preferredId === undefined ? selectedProfileRef.current : preferredId;
    const selected = rows.some((profile) => profile.id === preferred)
      ? preferred
      : rows.find((profile) => profile.is_active)?.id ?? rows[0]?.id ?? null;
    notifyProfileChange(selected);
    return rows;
  }, [notifyProfileChange]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([flowSessionApi.listProfiles(), flowSessionApi.currentLoginSession()])
      .then(([rows, session]) => {
        if (cancelled) return;
        setProfiles(rows);
        setLoginSession(session);
        const active = session?.profile_id ?? rows.find((profile) => profile.is_active)?.id ?? rows[0]?.id ?? null;
        selectedProfileRef.current = active;
        setSelectedProfileId(active);
        onProfileChangeRef.current?.(active);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(readableError(reason));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!loginSession || terminalSessionStates.has(loginSession.status)) return;
    let cancelled = false;
    let desktopReady = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      if (cancelled) return;
      try {
        const current = await flowSessionApi.getLoginSession(loginSession.id);
        if (cancelled) return;
        setLoginSession(current);
        if (current.status === "OPEN" && !desktopReady) {
          const access = await flowSessionApi.createDesktopAccess(current.id);
          if (cancelled) return;
          desktopReady = true;
          setDesktopUrl(access.url);
          setDesktopKey((value) => value + 1);
        }
        if (terminalSessionStates.has(current.status)) {
          setDesktopUrl(null);
          if (current.status !== "CLOSED") {
            setError({ message: sessionLabels[current.status], code: current.error_code ?? undefined });
          }
          return;
        }
      } catch (reason) {
        if (!cancelled) setError(readableError(reason));
      }
      timer = setTimeout(poll, 1500);
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [loginSession?.id, loginSession?.status]);

  const handleProfileSelection = (profileId: string) => {
    setError(null);
    setNotice("");
    notifyProfileChange(profileId || null);
  };

  const createProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setBusyAction("create");
    setError(null);
    setNotice("");
    try {
      const profile = await flowSessionApi.createProfile(name);
      setNewName("");
      await refreshProfiles(profile.id);
      setNotice("Đã tạo hồ sơ Flow. Phiên đăng nhập sẽ được lưu trong hồ sơ này.");
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusyAction(null);
    }
  };

  const activateProfile = async () => {
    if (!selectedProfileId) return;
    setBusyAction("activate");
    setError(null);
    setNotice("");
    try {
      await flowSessionApi.activateProfile(selectedProfileId);
      await refreshProfiles(selectedProfileId);
      setNotice("Hồ sơ này hiện là hồ sơ Flow mặc định của workspace.");
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusyAction(null);
    }
  };

  const checkProfile = async () => {
    if (!selectedProfileId) return;
    setBusyAction("check");
    setError(null);
    setNotice("Đang chờ worker kiểm tra trạng thái Flow.");
    try {
      let command = await flowSessionApi.checkProfile(selectedProfileId);
      const deadline = Date.now() + 15 * 60 * 1000;
      while (["PENDING", "RUNNING"].includes(command.state) && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        command = await flowSessionApi.getCommand(command.id);
      }
      const rows = await refreshProfiles(selectedProfileId);
      const updated = rows.find((profile) => profile.id === selectedProfileId);
      setNotice(updated ? `Flow: ${providerLabels[updated.state]}.` : "Đã hoàn tất kiểm tra Flow.");
      if (command.state === "FAILED") {
        setError({ message: "Worker không thể kiểm tra hồ sơ Flow.", code: command.error_code ?? undefined });
      } else if (["PENDING", "RUNNING"].includes(command.state)) {
        setNotice("Lệnh kiểm tra vẫn đang chờ worker; trạng thái chưa được xác nhận.");
      }
    } catch (reason) {
      setError(readableError(reason));
      setNotice("");
    } finally {
      setBusyAction(null);
    }
  };

  const startLogin = async () => {
    if (!selectedProfileId) {
      setError({ message: "Tạo hoặc chọn một hồ sơ Flow trước khi mở phiên đăng nhập." });
      return;
    }
    setBusyAction("login");
    setError(null);
    setNotice("");
    setDesktopUrl(null);
    try {
      const session = await flowSessionApi.startLoginSession(selectedProfileId);
      setLoginSession(session);
      setNotice("Yêu cầu đã được lưu. Desktop sẽ mở sau khi worker nhận tài nguyên video.");
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusyAction(null);
    }
  };

  const renewDesktopAccess = async () => {
    if (!loginSession || loginSession.status !== "OPEN") return;
    setBusyAction("desktop");
    setError(null);
    try {
      const access = await flowSessionApi.createDesktopAccess(loginSession.id);
      setDesktopUrl(access.url);
      setDesktopKey((value) => value + 1);
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusyAction(null);
    }
  };

  const closeLogin = async () => {
    if (!loginSession) return;
    setBusyAction("close");
    setError(null);
    setDesktopUrl(null);
    try {
      const updated = await flowSessionApi.closeLoginSession(loginSession.id);
      setLoginSession(updated);
      setNotice("Đã gửi lệnh đóng desktop. Hồ sơ lưu trên volume dùng lại cho lần đăng nhập sau.");
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusyAction(null);
    }
  };

  const selectedProfile = profiles.find((profile) => profile.id === selectedProfileId) ?? null;
  const loginPending = Boolean(loginSession && !terminalSessionStates.has(loginSession.status));

  return (
    <Card className="gap-0">
      <CardHeader className="border-b border-border/70 pb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-base">
              <MonitorUp aria-hidden="true" className="size-4 text-primary" />
              Flow profiles
            </CardTitle>
            <CardDescription>
              Mỗi hồ sơ giữ phiên Google trong volume riêng của workspace. Desktop chỉ mở khi worker đã nhận lease.
            </CardDescription>
          </div>
          {selectedProfile && (
            <Badge variant={stateVariant(selectedProfile.state)}>
              {providerLabels[selectedProfile.state]}
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="grid gap-5 pt-4">
        {error && (
          <Alert variant="destructive">
            <AlertCircle aria-hidden="true" />
            <AlertTitle>{error.code ?? "Không thể hoàn tất thao tác"}</AlertTitle>
            <AlertDescription>{error.message}</AlertDescription>
          </Alert>
        )}
        {notice && !error && <p className="text-sm text-muted-foreground" role="status">{notice}</p>}

        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(16rem,0.8fr)]">
          <div className="grid content-start gap-3">
            <div className="grid gap-2">
              <label htmlFor="flow-profile" className="text-sm font-medium">Hồ sơ Flow</label>
              <select
                id="flow-profile"
                className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
                value={selectedProfileId ?? ""}
                onChange={(event) => handleProfileSelection(event.currentTarget.value)}
                disabled={loading || profiles.length === 0 || loginPending}
              >
                <option value="" disabled>{loading ? "Đang tải hồ sơ..." : "Chọn hồ sơ"}</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name}{profile.is_active ? " · Mặc định" : ""}
                  </option>
                ))}
              </select>
              {selectedProfile && (
                <p className="text-xs text-muted-foreground">
                  Lựa chọn này được gửi cho lần tạo hoặc tiếp tục run hiện tại.
                  {selectedProfile.is_active ? " Đây cũng là hồ sơ mặc định của workspace." : ""}
                </p>
              )}
            </div>

            <form className="flex flex-col gap-2 sm:flex-row" onSubmit={createProfile}>
              <label htmlFor="flow-profile-name" className="sr-only">Tên hồ sơ mới</label>
              <Input
                id="flow-profile-name"
                value={newName}
                onChange={(event) => setNewName(event.currentTarget.value)}
                placeholder="Ví dụ: Kênh chính"
                maxLength={100}
                autoComplete="off"
                disabled={busyAction !== null || loginPending}
              />
              <Button type="submit" variant="outline" disabled={!newName.trim() || busyAction !== null || loginPending}>
                {busyAction === "create" ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Plus aria-hidden="true" />}
                Tạo hồ sơ
              </Button>
            </form>

            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" onClick={activateProfile} disabled={!selectedProfileId || busyAction !== null || loginPending || selectedProfile?.is_active}>
                {busyAction === "activate" ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Check aria-hidden="true" />}
                Đặt làm mặc định
              </Button>
              <Button type="button" variant="outline" onClick={checkProfile} disabled={!selectedProfileId || busyAction !== null || loginPending}>
                {busyAction === "check" ? <Loader2 className="animate-spin" aria-hidden="true" /> : <RefreshCw aria-hidden="true" />}
                Kiểm tra trạng thái
              </Button>
              <Button type="button" onClick={startLogin} disabled={!selectedProfileId || busyAction !== null || loginPending}>
                {busyAction === "login" ? <Loader2 className="animate-spin" aria-hidden="true" /> : <LogIn aria-hidden="true" />}
                Mở phiên đăng nhập
              </Button>
            </div>
          </div>

          <div className="grid content-start gap-2" aria-label="Trạng thái nhà cung cấp Flow">
            <ProviderState label="Flow Music" state={selectedProfile?.flow_music_state ?? "UNKNOWN"} />
            <ProviderState label="Google Flow" state={selectedProfile?.google_flow_state ?? "UNKNOWN"} />
            <p className="px-1 text-xs leading-relaxed text-muted-foreground">
              Chỉ trạng thái được xác nhận từ trang provider mới hiển thị là sẵn sàng. Hết quota và cần đăng nhập được báo riêng.
            </p>
          </div>
        </div>

        {profiles.length === 0 && !loading && (
          <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            Workspace chưa có hồ sơ Flow. Tạo hồ sơ để bắt đầu đăng nhập trong desktop riêng.
          </p>
        )}

        {loginSession && (
          <section className="grid gap-3 border-t border-border/70 pt-4" aria-labelledby="flow-session-heading">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 id="flow-session-heading" className="font-medium">Phiên đăng nhập</h3>
                <p className="text-sm text-muted-foreground" role="status">{sessionLabels[loginSession.status]}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {loginSession.status === "OPEN" && (
                  <Button type="button" variant="outline" onClick={renewDesktopAccess} disabled={busyAction !== null}>
                    {busyAction === "desktop" ? <Loader2 className="animate-spin" aria-hidden="true" /> : <RefreshCw aria-hidden="true" />}
                    Làm mới desktop
                  </Button>
                )}
                {!terminalSessionStates.has(loginSession.status) && (
                  <Button type="button" variant="destructive" onClick={closeLogin} disabled={busyAction !== null}>
                    {busyAction === "close" ? <Loader2 className="animate-spin" aria-hidden="true" /> : <X aria-hidden="true" />}
                    Đóng phiên
                  </Button>
                )}
              </div>
            </div>
            {desktopUrl && loginSession.status === "OPEN" && (
              <div className="overflow-hidden rounded-lg border border-border/80 bg-muted/30">
                <iframe
                  key={desktopKey}
                  src={desktopUrl}
                  title="Desktop đăng nhập Google Flow"
                  className="aspect-video min-h-80 w-full bg-black sm:min-h-[32rem]"
                  referrerPolicy="same-origin"
                />
              </div>
            )}
            {loginSession.status === "OPEN" && !desktopUrl && (
              <p className="text-sm text-muted-foreground" role="status">Đang cấp quyền ngắn hạn cho desktop...</p>
            )}
          </section>
        )}
      </CardContent>
    </Card>
  );
}

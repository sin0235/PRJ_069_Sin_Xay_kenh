"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Smartphone,
  RefreshCw,
  Plus,
  ShieldCheck,
  CheckCircle2,
  ExternalLink,
  Settings,
  BarChart3,
  Users,
  Video,
  Heart,
  Database,
  Radio,
  AlertCircle,
  Loader2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

import { TikTokService } from "@/services/tiktok-service";
import { TikTokChannel } from "@/types";
import { useCreatorStore } from "@/stores/use-creator-store";

function formatCount(value: number | null) {
  if (value == null) return "—";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString("vi-VN");
}

export default function ChannelsPage() {
  const router = useRouter();
  const { activeChannelId, setActiveChannelId } = useCreatorStore();
  const [channels, setChannels] = React.useState<TikTokChannel[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [isLiveDb, setIsLiveDb] = React.useState(false);

  // State Modal Kết Nối Kênh Thật
  const [openModal, setOpenModal] = React.useState(false);
  const [inputUsername, setInputUsername] = React.useState("");
  const [verifying, setVerifying] = React.useState(false);
  const [verifyError, setVerifyError] = React.useState<string | null>(null);
  const [verifySuccess, setVerifySuccess] = React.useState<string | null>(null);

  const loadChannels = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await TikTokService.getConnectedChannels();
      setChannels(data);
      setIsLiveDb(data.some((channel) => channel.status === "connected"));
      if (data.length > 0) {
        if (!activeChannelId) {
          setActiveChannelId(data[0].id);
        }
      }
    } catch {
      // Fallback
    } finally {
      setLoading(false);
    }
  }, [activeChannelId, setActiveChannelId]);

  React.useEffect(() => {
    loadChannels();
  }, [loadChannels]);

  // Xử lý xác minh và kết nối kênh TikTok THẬT 100%
  const handleVerifyAndConnect = async () => {
    if (!inputUsername.trim()) {
      setVerifyError("Vui lòng nhập @username hoặc link kênh TikTok của bạn.");
      return;
    }

    setVerifying(true);
    setVerifyError(null);
    setVerifySuccess(null);

    try {
      const connected = await TikTokService.verifyAndConnectChannel(inputUsername.trim());
      setVerifySuccess(`Xác minh thành công kênh ${connected.displayName} (${connected.username})! Đang cập nhật hệ thống...`);
      setTimeout(async () => {
        await loadChannels();
        setActiveChannelId(connected.id);
        setVerifying(false);
        setOpenModal(false);
        setInputUsername("");
        setVerifySuccess(null);
      }, 1500);
    } catch (err: any) {
      setVerifyError(err.message || "Không thể xác minh kênh TikTok. Vui lòng kiểm tra lại username.");
      setVerifying(false);
    }
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Quản Lý Kênh TikTok (Channels)
            </h1>
            <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
              Quản lý kết nối
            </Badge>
            {isLiveDb && (
              <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 bg-emerald-500/10 text-xs font-semibold gap-1">
                <Database className="size-3" /> Dữ liệu trực tiếp
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Kết nối tài khoản TikTok và đồng bộ chỉ số kênh tự động theo thời gian thực.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={loadChannels}
            disabled={loading}
            className="h-8 text-xs font-semibold rounded-lg gap-1.5"
          >
            <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Đồng bộ lại</span>
          </Button>

          <Button
            size="sm"
            onClick={() => {
              setVerifyError(null);
              setVerifySuccess(null);
              setOpenModal(true);
            }}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
          >
            <Plus className="size-3.5" />
            <span>Kết Nối Kênh TikTok Thật</span>
          </Button>
        </div>
      </div>

      {/* Security Callout */}
      <div className="flex items-center justify-between p-3.5 rounded-xl bg-muted/40 border border-border/80 text-xs">
        <div className="flex items-center gap-2.5">
          <ShieldCheck className="size-4 text-emerald-500 shrink-0" />
          <span className="text-muted-foreground">
            Chỉ số chỉ hiển thị khi backend có dữ liệu xác minh; thông tin còn thiếu sẽ được để trống.
          </span>
        </div>

        <span className="text-[10px] text-primary font-medium">
          Dữ liệu từ backend
        </span>
      </div>

      {/* Empty State */}
      {!loading && channels.length === 0 && (
        <Card className="rounded-2xl border-dashed border-2 p-12 text-center space-y-4 bg-muted/20">
          <div className="mx-auto size-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary">
            <Radio className="size-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-foreground">Chưa có kênh TikTok nào được kết nối</h3>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              Hãy nhập @username hoặc link kênh TikTok của bạn để hệ thống tự động xác minh và đồng bộ số liệu thật vào hệ điều hành Sin OS.
            </p>
          </div>
          <Button
            onClick={() => setOpenModal(true)}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5"
          >
            <Plus className="size-3.5" />
            <span>Kết Nối Ngay</span>
          </Button>
        </Card>
      )}

      {/* Channel Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {channels.map((channel) => {
          const isActive = channel.id === activeChannelId;

          return (
            <Card
              key={channel.id}
              className={`rounded-2xl border transition-all p-5 space-y-4 bg-card flex flex-col justify-between shadow-xs ${
                isActive ? "border-primary ring-1 ring-primary/40 shadow-md" : "border-border/80 hover:border-primary/40"
              }`}
            >
              <div className="space-y-3">
                {/* Channel Header */}
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <Avatar className="size-12 border-2 border-primary/20">
                      <AvatarImage src={channel.avatarUrl} alt={channel.username} />
                      <AvatarFallback className="font-bold text-primary">
                      {channel.username ? channel.username.slice(1, 3).toUpperCase() : <Smartphone className="size-4" aria-hidden="true" />}
                      </AvatarFallback>
                    </Avatar>

                    <div>
                      <h3 className="text-sm font-bold text-foreground line-clamp-1">{channel.displayName}</h3>
                      <div className="text-xs text-primary font-mono font-medium">{channel.username}</div>
                    </div>
                  </div>

                  <span className="flex items-center gap-1 text-[10px] text-muted-foreground px-2 py-0.5 rounded-full font-semibold">
                    <span className={`size-1.5 rounded-full ${channel.status === "connected" ? "bg-emerald-500" : "bg-muted-foreground"}`} />
                    {channel.status === "connected" ? "Đã kết nối" : channel.status === "expired" ? "Hết hạn" : "Chưa khả dụng"}
                  </span>
                </div>

                {/* Bio */}
                <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                  {channel.bio || "Chưa có mô tả kênh."}
                </p>

                {/* Core Stats (Ground Truth) */}
                <div className="grid grid-cols-3 gap-2 p-2.5 rounded-xl bg-muted/40 border border-border/50 text-center font-mono">
                  <div>
                    <span className="text-[10px] text-muted-foreground block">Followers</span>
                    <span className="text-xs font-bold text-foreground">
                      {formatCount(channel.followersCount)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-muted-foreground block">Video</span>
                    <span className="text-xs font-bold text-foreground">
                      {formatCount(channel.videoCount)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-muted-foreground block">Tổng Likes</span>
                    <span className="text-xs font-bold text-primary">
                      {formatCount(channel.likesCount)}
                    </span>
                  </div>
                </div>

                <div className="text-[10px] text-muted-foreground font-mono flex items-center justify-between">
                  <span>{channel.connectedAt ? `Xác minh: ${new Date(channel.connectedAt).toLocaleDateString("vi-VN")}` : "Chưa có thời điểm xác minh"}</span>
                  <span>{channel.status === "connected" ? "Đã xác thực" : "Chưa xác thực"}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-2 pt-2 border-t border-border/50">
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => router.push("/analytics")}
                    className="h-8 text-xs font-medium rounded-lg gap-1"
                  >
                    <BarChart3 className="size-3" />
                    <span>Analytics</span>
                  </Button>

                  <Button
                    variant={isActive ? "secondary" : "default"}
                    size="sm"
                    onClick={() => setActiveChannelId(channel.id)}
                    className="h-8 text-xs font-semibold rounded-lg"
                  >
                    {isActive ? "Đang chọn" : "Kích hoạt kênh"}
                  </Button>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Modal Kết Nối Kênh TikTok Thật (Ground Truth) */}
      <Dialog open={openModal} onOpenChange={setOpenModal}>
        <DialogContent className="max-w-md rounded-2xl p-6 space-y-4">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold flex items-center gap-2">
              <Radio className="size-5 text-primary" />
              <span>Kết Nối Kênh TikTok Thật 100%</span>
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Nhập tên tài khoản hoặc liên kết TikTok của bạn. Hệ thống sẽ tự động xác minh và đồng bộ số liệu kênh vào không gian làm việc.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-foreground">
                Tên tài khoản hoặc Link TikTok:
              </label>
              <Input
                placeholder="Ví dụ: @sin_official hoặc https://www.tiktok.com/@tiktok"
                value={inputUsername}
                onChange={(e) => setInputUsername(e.target.value)}
                disabled={verifying}
                className="h-9 text-xs rounded-xl"
              />
            </div>

            {verifyError && (
              <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/30 text-destructive text-xs flex items-start gap-2">
                <AlertCircle className="size-4 shrink-0 mt-0.5" />
                <span>{verifyError}</span>
              </div>
            )}

            {verifySuccess && (
              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 text-xs flex items-start gap-2">
                <CheckCircle2 className="size-4 shrink-0 mt-0.5" />
                <span>{verifySuccess}</span>
              </div>
            )}


          </div>

          <DialogFooter className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOpenModal(false)}
              disabled={verifying}
              className="h-8 text-xs rounded-lg"
            >
              Hủy
            </Button>
            <Button
              size="sm"
              onClick={handleVerifyAndConnect}
              disabled={verifying}
              className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5"
            >
              {verifying && <Loader2 className="size-3.5 animate-spin" />}
              <span>{verifying ? "Đang xác minh Live..." : "Xác Minh & Kết Nối Ngay"}</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

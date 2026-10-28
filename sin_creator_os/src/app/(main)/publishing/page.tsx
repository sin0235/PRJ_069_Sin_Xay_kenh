"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Send,
  Calendar,
  Clock,
  Sparkles,
  Lock,
  Globe,
  Users,
  CheckCircle2,
  AlertCircle,
  Smartphone,
  Heart,
  MessageCircle,
  Bookmark,
  Share2,
  Hash,
  Eye,
  Film,
  ExternalLink,
  Trash2,
  RefreshCw,
  Layers,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

import { useCreatorStore } from "@/stores/use-creator-store";
import { PublishingService, PublishedLinkItem } from "@/services/publishing-service";

export default function PublishingPage() {
  const router = useRouter();
  const { channels, activeChannelId, setActiveChannelId } = useCreatorStore();

  const [activeTab, setActiveTab] = React.useState<"ready" | "scheduled" | "published" | "draft">("ready");

  // Post composer state
  const [caption, setCaption] = React.useState("");
  const [hashtags, setHashtags] = React.useState("");
  const [scheduleTime, setScheduleTime] = React.useState("");
  const [privacy, setPrivacy] = React.useState("public");
  const [allowComments, setAllowComments] = React.useState(true);
  const [allowDuet, setAllowDuet] = React.useState(true);
  const [allowStitch, setAllowStitch] = React.useState(true);


  // Danh sach bai dang tu Backend
  const [publishedLinks, setPublishedLinks] = React.useState<PublishedLinkItem[]>([]);
  const [isLoadingLinks, setIsLoadingLinks] = React.useState(false);

  const fetchPublishedLinks = React.useCallback(async () => {
    setIsLoadingLinks(true);
    try {
      const items = await PublishingService.listPublishedLinks();
      setPublishedLinks(items);
    } catch {
      // Fallback
    } finally {
      setIsLoadingLinks(false);
    }
  }, []);

  React.useEffect(() => {
    fetchPublishedLinks();
  }, [fetchPublishedLinks]);

  const activeChannel = channels.find((channel) => channel.id === activeChannelId);

  const handleDetach = async (linkId: string) => {
    const ok = await PublishingService.detachPublishedLink(linkId);
    if (ok) {
      setPublishedLinks((prev) => prev.filter((p) => p.id !== linkId));
    }
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Trung Tâm Xuất Bản Đa Kênh (Publishing Hub)
            </h1>
            <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
              Chưa tích hợp xuất bản trực tiếp
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Lên lịch đăng bài, kiểm duyệt Safe Zone và điều phối phát hành bài đăng TikTok.
          </p>
        </div>

        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as any)}
          className="h-8"
        >
          <TabsList className="h-8 p-1 bg-muted/60">
            <TabsTrigger value="ready" className="text-xs px-2.5 h-6">Soạn thảo</TabsTrigger>
            <TabsTrigger value="scheduled" className="text-xs px-2.5 h-6">Đã lên lịch</TabsTrigger>
            <TabsTrigger value="published" className="text-xs px-2.5 h-6">
              Đã phát ({publishedLinks.length})
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {activeTab === "ready" ? (
        /* Post Composer Layout: Left Form (7 cols) + Right Phone Preview (5 cols) */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Form: Composer Controls */}
          <div className="lg:col-span-7 space-y-4">
            <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4 bg-card">
              <div className="flex items-center justify-between border-b border-border/60 pb-3">
                <span className="text-sm font-bold text-foreground flex items-center gap-2">
                  <Send className="size-4 text-primary" /> Soạn Bài Đăng TikTok (Post Composer)
                </span>
                <span className="text-[11px] text-muted-foreground font-mono">
                  Kênh: {activeChannel?.username || "Chưa kết nối kênh"}
                </span>
              </div>

              {/* Select Channel */}
              <div className="space-y-1.5 text-xs">
                <label className="text-[11px] font-semibold text-muted-foreground block">
                  Tài Khoản TikTok Đích:
                </label>
                <Select value={activeChannelId || undefined} onValueChange={setActiveChannelId}>
                  <SelectTrigger className="h-9 rounded-xl text-xs bg-background">
                  <SelectValue placeholder="Chưa có kênh đã kết nối" />
                  </SelectTrigger>
                  <SelectContent className="rounded-xl">
                    {channels.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.displayName} ({c.username})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Caption & Hashtags */}
              <div className="space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-semibold text-muted-foreground">
                    Mô Tả Bài Viết (Caption):
                  </label>
                  <span className="text-[10px] text-muted-foreground font-mono">
                    {caption.length} / 2200 ký tự
                  </span>
                </div>
                <Textarea
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                  rows={4}
                  className="text-xs rounded-xl bg-background border-border/80 focus-visible:ring-primary/30"
                />
              </div>

              <div className="space-y-1.5 text-xs">
                <label className="text-[11px] font-semibold text-muted-foreground block">
                  Hashtags Xu Hướng:
                </label>
                <Input
                  value={hashtags}
                  onChange={(e) => setHashtags(e.target.value)}
                  className="h-8 text-xs rounded-lg"
                />
              </div>

              {/* Schedule Date & Time */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="space-y-1.5">
                  <label className="text-[11px] font-semibold text-muted-foreground block">
                    Thời Gian Phát Sóng:
                  </label>
                  <Input
                    type="datetime-local"
                    value={scheduleTime}
                    onChange={(e) => setScheduleTime(e.target.value)}
                    className="h-9 text-xs rounded-xl font-mono"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-semibold text-muted-foreground block">
                    Quyền Riêng Tư:
                  </label>
                  <Select value={privacy} onValueChange={setPrivacy}>
                    <SelectTrigger className="h-9 rounded-xl text-xs bg-background">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="rounded-xl">
                      <SelectItem value="public">Công khai (Public)</SelectItem>
                      <SelectItem value="friends">Bạn bè (Friends)</SelectItem>
                      <SelectItem value="private">Riêng tư (Private)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Interaction Permissions */}
              <div className="pt-2 border-t border-border/60 space-y-2 text-xs">
                <span className="text-[11px] font-semibold text-muted-foreground block">
                  Cài Đặt Tương Tác:
                </span>
                <div className="grid grid-cols-3 gap-3">
                  <div className="flex items-center justify-between p-2 rounded-lg bg-muted/30 border border-border/40">
                    <span className="text-[11px]">Bình luận</span>
                    <Switch checked={allowComments} onCheckedChange={setAllowComments} />
                  </div>
                  <div className="flex items-center justify-between p-2 rounded-lg bg-muted/30 border border-border/40">
                    <span className="text-[11px]">Duet</span>
                    <Switch checked={allowDuet} onCheckedChange={setAllowDuet} />
                  </div>
                  <div className="flex items-center justify-between p-2 rounded-lg bg-muted/30 border border-border/40">
                    <span className="text-[11px]">Stitch</span>
                    <Switch checked={allowStitch} onCheckedChange={setAllowStitch} />
                  </div>
                </div>
              </div>

              {/* Action Bar */}
              <div className="flex items-center justify-between pt-3 border-t border-border/60">
                <Button variant="outline" size="sm" className="h-9 text-xs rounded-xl">
                  Lưu Bản Nháp
                </Button>

                <Button disabled className="h-9 px-5 rounded-xl text-xs font-semibold gap-1.5 shadow-sm">
                  <Send className="size-3.5" />
                  <span>Xuất bản trực tiếp chưa khả dụng</span>
                </Button>
              </div>

              <p className="text-xs text-muted-foreground">
                Màn hình này chưa kết nối chức năng xuất bản hoặc lên lịch TikTok.
              </p>
            </Card>
          </div>

          {/* Right Preview: Real Phone Mockup Preview */}
          <div className="lg:col-span-5 flex flex-col items-center justify-center">
            <div className="relative w-[280px] aspect-[9/18] rounded-[36px] overflow-hidden border-[6px] border-zinc-800 bg-black shadow-2xl flex flex-col justify-between">
              {/* Video Preview */}
              <div className="absolute inset-0 flex items-center justify-center bg-zinc-900 text-white/70"><Film className="size-10" aria-hidden="true" /></div>
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30" />

              {/* Top Phone Header */}
              <div className="relative z-10 px-4 pt-3 flex justify-between text-white text-[10px] font-bold">
                <span>9:41</span>
                <span>TikTok Preview</span>
              </div>

              {/* Right Buttons Overlay in TikTok */}
              <div className="absolute right-2 bottom-16 flex flex-col items-center gap-3 z-10 text-white text-[10px]">
                <div className="size-8 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center">
                  <Heart className="size-4 fill-white text-white" />
                </div>
                <span>—</span>
                <div className="size-8 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center">
                  <MessageCircle className="size-4 text-white" />
                </div>
                <span>—</span>
                <div className="size-8 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center">
                  <Bookmark className="size-4 fill-white text-white" />
                </div>
                <span>—</span>
                <div className="size-8 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center">
                  <Share2 className="size-4 text-white" />
                </div>
                <span>Share</span>
              </div>

              {/* Bottom Caption and Creator Details */}
              <div className="relative z-10 p-3 text-white space-y-1.5 text-xs">
                <div className="font-bold">{activeChannel?.username || "Chưa kết nối kênh"}</div>
                <p className="text-[11px] text-zinc-200 line-clamp-3 leading-snug">
                  {caption}
                </p>
                <div className="text-[10px] text-amber-300 font-mono">
                  {hashtags}
                </div>
              </div>
            </div>
            <span className="text-[11px] text-muted-foreground mt-2 font-mono">
              Mô phỏng hiển thị trên ứng dụng TikTok
            </span>
          </div>
        </div>
      ) : (
        /* Published & Scheduled Links Table */
        <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-border/60 pb-3">
            <div>
              <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                <Layers className="size-4 text-primary" /> Danh Sách Bài Đăng Hệ Thống
              </h3>
              <p className="text-xs text-muted-foreground">
                Tổng cộng {publishedLinks.length} bài đăng đã liên kết với kịch bản và kênh TikTok.
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={fetchPublishedLinks}
              disabled={isLoadingLinks}
              className="h-8 text-xs rounded-lg gap-1.5"
            >
              <RefreshCw className={`size-3.5 ${isLoadingLinks ? "animate-spin" : ""}`} />
              <span>Làm mới</span>
            </Button>
          </div>

          {isLoadingLinks ? (
            <div className="py-12 flex flex-col items-center justify-center text-xs text-muted-foreground gap-2">
              <RefreshCw className="size-5 animate-spin text-primary" />
              <span>Đang tải danh sách bài đăng từ máy chủ...</span>
            </div>
          ) : publishedLinks.length === 0 ? (
            <div className="py-12 flex flex-col items-center justify-center text-xs text-muted-foreground gap-2">
              <Send className="size-6 text-muted-foreground/40" />
              <span>Chưa có bài đăng nào được liên kết. Hãy lên lịch bài đăng đầu tiên ở tab Soạn thảo!</span>
            </div>
          ) : (
            <div className="divide-y divide-border/60">
              {publishedLinks.map((link) => (
                <div key={link.id} className="py-3 flex items-center justify-between gap-4 text-xs">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-foreground font-mono">ID: {link.external_post_id}</span>
                      <Badge variant="outline" className="text-[10px] uppercase font-mono">
                        {link.platform}
                      </Badge>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                          link.status === "ACTIVE"
                            ? "bg-emerald-500/10 text-emerald-600"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {link.status}
                      </span>
                    </div>
                    <div className="text-[11px] text-muted-foreground flex items-center gap-3 font-mono">
                      <span>Kịch bản: {link.script_draft_version_id}</span>
                      <span>Ngày tạo: {new Date(link.created_at).toLocaleString("vi-VN")}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      asChild
                      className="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground"
                    >
                      <a href={link.external_post_url} target="_blank" rel="noreferrer">
                        <ExternalLink className="size-3.5 mr-1" />
                        <span>Xem video</span>
                      </a>
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDetach(link.id)}
                      className="h-8 px-2.5 text-xs text-destructive hover:bg-destructive/10"
                    >
                      <Trash2 className="size-3.5 mr-1" />
                      <span>Gỡ liên kết</span>
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

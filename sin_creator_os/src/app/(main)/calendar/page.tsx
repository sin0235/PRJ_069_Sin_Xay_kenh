"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Clock,
  Sparkles,
  Plus,
  Play,
  Share2,
  CheckCircle2,
  Flame,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { PublishingService } from "@/services/publishing-service";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

interface ScheduledPost {
  id: string;
  day: number; // day of current month (e.g. 21, 22, 23)
  dateStr: string;
  time: string;
  title: string;
  thumbnailUrl: string;
  status: "scheduled" | "published" | "draft";
  channel: string;
  pillar: string;
  durationSec: number;
}

const scheduledPosts: ScheduledPost[] = [
  {
    id: "post_01",
    day: 19,
    dateStr: "19/10/2026",
    time: "19:30",
    title: "Cách 1 AI Agent tự động viết 30 kịch bản TikTok trong 60 giây",
    thumbnailUrl: "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&auto=format&fit=crop&q=80",
    status: "published",
    channel: "@bahagroup.creator",
    pillar: "AI Workflow",
    durationSec: 28,
  },
  {
    id: "post_02",
    day: 21,
    dateStr: "21/10/2026",
    time: "18:00",
    title: "Bí Mật Đằng Sau Video Triệu View Bằng Voice Clone ElevenLabs",
    thumbnailUrl: "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=400&auto=format&fit=crop&q=80",
    status: "scheduled",
    channel: "@bahagroup.creator",
    pillar: "AI Audio",
    durationSec: 31,
  },
  {
    id: "post_03",
    day: 22,
    dateStr: "22/10/2026",
    time: "11:30",
    title: "Cách Setup Safe Zone TikTok Để Không Bị Che Chữ & Nút Like",
    thumbnailUrl: "https://images.unsplash.com/photo-1634017839464-5c339ebe3cb4?w=400&auto=format&fit=crop&q=80",
    status: "scheduled",
    channel: "@bahagroup.creator",
    pillar: "Technical Tips",
    durationSec: 22,
  },
  {
    id: "post_04",
    day: 24,
    dateStr: "24/10/2026",
    time: "20:15",
    title: "Lộ Trình Tự Động Hóa Kênh TikTok Từ Con Số 0 Với AI Agent",
    thumbnailUrl: "https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?w=400&auto=format&fit=crop&q=80",
    status: "scheduled",
    channel: "@bahagroup.creator",
    pillar: "Automation",
    durationSec: 32,
  },
];

export default function CalendarPage() {
  const router = useRouter();
  const [view, setView] = React.useState<"month" | "week" | "list">("month");
  const [selectedPost, setSelectedPost] = React.useState<ScheduledPost | null>(null);
  const [posts, setPosts] = React.useState<ScheduledPost[]>(scheduledPosts);

  // Nạp bài đăng thật từ Backend Publishing API
  React.useEffect(() => {
    PublishingService.listPublishedLinks()
      .then((items) => {
        if (items && items.length > 0) {
          const mapped: ScheduledPost[] = items.map((item, idx) => {
            const pubDate = item.published_at ? new Date(item.published_at) : new Date(item.created_at);
            const day = pubDate.getDate() || 22;
            const hours = String(pubDate.getHours()).padStart(2, "0");
            const mins = String(pubDate.getMinutes()).padStart(2, "0");
            return {
              id: item.id,
              day,
              dateStr: `${day}/10/2026`,
              time: `${hours}:${mins}`,
              title: `Video TikTok #${item.external_post_id} (${item.script_draft_version_id || "Bản nháp"})`,
              thumbnailUrl:
                idx % 2 === 0
                  ? "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&auto=format&fit=crop&q=80"
                  : "https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?w=400&auto=format&fit=crop&q=80",
              status: item.status === "ACTIVE" ? "published" : "scheduled",
              channel: item.channel_id ? `@${item.channel_id}` : "@bahagroup.creator",
              pillar: "AI Workflow",
              durationSec: 28,
            };
          });
          setPosts([...mapped, ...scheduledPosts]);
        }
      })
      .catch(() => {});
  }, []);

  // Calendar days grid for October 2026
  const daysInMonth = Array.from({ length: 31 }, (_, i) => i + 1);

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Lịch Xuất Bản Video (Content Calendar)
            </h1>
            <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
              Tháng 10, 2026
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Lập lịch đăng bài TikTok tự động, quản lý khung giờ vàng và nhịp độ xuất bản nội dung.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Tabs value={view} onValueChange={(v) => setView(v as any)} className="h-8">
            <TabsList className="h-8 p-1 bg-muted/60">
              <TabsTrigger value="month" className="text-xs px-2.5 h-6">Tháng</TabsTrigger>
              <TabsTrigger value="week" className="text-xs px-2.5 h-6">Tuần</TabsTrigger>
              <TabsTrigger value="list" className="text-xs px-2.5 h-6">Danh sách</TabsTrigger>
            </TabsList>
          </Tabs>

          <Button
            size="sm"
            onClick={() => router.push("/publishing")}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
          >
            <Plus className="size-3.5" />
            <span>Lên Lịch Video Mới</span>
          </Button>
        </div>
      </div>

      {/* Month View Grid */}
      {view === "month" && (
        <Card className="rounded-2xl border-border/80 shadow-xs p-4 bg-card">
          <div className="grid grid-cols-7 gap-2 text-center text-xs font-bold text-muted-foreground pb-3 border-b border-border/60">
            <div>T2</div>
            <div>T3</div>
            <div>T4</div>
            <div>T5</div>
            <div>T6</div>
            <div>T7</div>
            <div className="text-primary font-bold">CN</div>
          </div>

          <div className="grid grid-cols-7 gap-2 pt-3">
            {daysInMonth.map((day) => {
              const postsOnDay = posts.filter((p) => p.day === day);
              const isToday = day === 21;

              return (
                <div
                  key={day}
                  className={`min-h-[110px] rounded-xl border p-2 flex flex-col justify-between transition-colors ${
                    isToday
                      ? "border-primary bg-primary/5 shadow-xs"
                      : "border-border/60 bg-muted/10 hover:bg-muted/30"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span
                      className={`font-mono font-bold text-xs ${
                        isToday ? "text-primary" : "text-foreground"
                      }`}
                    >
                      {day}
                    </span>
                    {isToday && (
                      <Badge variant="outline" className="text-[9px] px-1 py-0 border-primary text-primary">
                        Hôm nay
                      </Badge>
                    )}
                  </div>

                  {/* Posts Cards inside Date Cell */}
                  <div className="space-y-1.5 mt-1 flex-1">
                    {postsOnDay.map((post) => (
                      <div
                        key={post.id}
                        onClick={() => setSelectedPost(post)}
                        className="p-1.5 rounded-lg border border-border/60 bg-card hover:border-primary/50 cursor-pointer shadow-xs text-left space-y-1"
                      >
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="font-mono text-primary font-bold">{post.time}</span>
                          <span className="text-[9px] font-mono text-muted-foreground">{post.durationSec}s</span>
                        </div>
                        <div className="text-[11px] font-semibold text-foreground line-clamp-1 leading-tight">
                          {post.title}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* List View */}
      {view === "list" && (
        <Card className="rounded-2xl border-border/80 shadow-xs overflow-hidden">
          <div className="divide-y divide-border/60">
            {posts.map((post) => (
              <div
                key={post.id}
                onClick={() => setSelectedPost(post)}
                className="p-4 flex items-center justify-between gap-4 hover:bg-muted/30 cursor-pointer transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="relative size-14 rounded-lg overflow-hidden bg-muted shrink-0">
                    <img src={post.thumbnailUrl} alt={post.title} className="size-full object-cover" />
                    <span className="absolute bottom-1 right-1 text-[9px] bg-black/70 text-white px-1 rounded font-mono">
                      {post.durationSec}s
                    </span>
                  </div>

                  <div>
                    <h4 className="text-xs font-bold text-foreground line-clamp-1">{post.title}</h4>
                    <div className="text-[11px] text-muted-foreground mt-0.5">
                      Kênh {post.channel} • Trụ cột: {post.pillar}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs font-mono shrink-0">
                  <span className="text-primary font-semibold flex items-center gap-1">
                    <Clock className="size-3.5" />
                    {post.dateStr} - {post.time}
                  </span>

                  <Badge
                    variant="outline"
                    className={`text-[10px] ${
                      post.status === "published"
                        ? "border-emerald-500/40 text-emerald-600 bg-emerald-500/10"
                        : "border-primary/40 text-primary bg-primary/5"
                    }`}
                  >
                    {post.status === "published" ? "Đã phát" : "Đã lên lịch"}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Quick Preview Dialog */}
      {selectedPost && (
        <Dialog open={!!selectedPost} onOpenChange={() => setSelectedPost(null)}>
          <DialogContent className="max-w-md rounded-2xl p-5">
            <DialogHeader>
              <DialogTitle className="text-base font-bold text-foreground">
                Chi Tiết Bài Đăng Đã Lên Lịch
              </DialogTitle>
              <DialogDescription className="text-xs">
                Kênh {selectedPost.channel} • Xuất bản lúc {selectedPost.time} ngày {selectedPost.dateStr}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 pt-2">
              <div className="relative aspect-[16/9] rounded-xl overflow-hidden bg-black/80">
                <img
                  src={selectedPost.thumbnailUrl}
                  alt={selectedPost.title}
                  className="size-full object-cover"
                />
              </div>

              <div className="space-y-1.5 text-xs">
                <span className="font-bold text-foreground text-sm block">{selectedPost.title}</span>
                <p className="text-muted-foreground leading-relaxed text-xs">
                  Video chuẩn tỉ lệ dọc 9:16, âm lượng -14 LUFS, Safe zone chuẩn TikTok 2026.
                </p>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-border/60">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push("/publishing")}
                  className="text-xs rounded-lg"
                >
                  Chỉnh sửa trong Composer
                </Button>

                <Button
                  size="sm"
                  onClick={() => router.push("/video-studio")}
                  className="text-xs rounded-lg bg-primary text-primary-foreground font-semibold"
                >
                  Mở Video Studio
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

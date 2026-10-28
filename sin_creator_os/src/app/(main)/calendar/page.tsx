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
  Film,
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
  status: "scheduled" | "published" | "draft";
  channel?: string;
  externalPostId?: string;
  externalPostUrl?: string;
}

export default function CalendarPage() {
  const router = useRouter();
  const [view, setView] = React.useState<"month" | "week" | "list">("month");
  const [selectedPost, setSelectedPost] = React.useState<ScheduledPost | null>(null);
  const [posts, setPosts] = React.useState<ScheduledPost[]>([]);

  const currentDate = new Date();
  const daysInMonth = Array.from({ length: new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0).getDate() }, (_, i) => i + 1);

  React.useEffect(() => {
    PublishingService.listPublishedLinks()
      .then((items) => {
        const mapped = items.flatMap((item) => {
          if (!item.published_at) return [];
          const publishedAt = new Date(item.published_at);
          if (publishedAt.getMonth() !== currentDate.getMonth() || publishedAt.getFullYear() !== currentDate.getFullYear()) return [];
          return [{
            id: item.id,
            day: publishedAt.getDate(),
            dateStr: publishedAt.toLocaleDateString("vi-VN"),
            time: publishedAt.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }),
            title: item.external_post_id,
            status: item.status === "ACTIVE" ? "published" as const : "draft" as const,
            channel: item.channel_id || undefined,
            externalPostId: item.external_post_id,
            externalPostUrl: item.external_post_url,
          }];
        });
        setPosts(mapped);
      })
      .catch(() => setPosts([]));
  }, []);

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
              {currentDate.toLocaleDateString("vi-VN", { month: "long", year: "numeric" })}
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
              const isToday = day === currentDate.getDate();

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
                    <div className="size-full flex items-center justify-center text-muted-foreground"><Film className="size-5" aria-hidden="true" /></div>
                  </div>

                  <div>
                    <h4 className="text-xs font-bold text-foreground line-clamp-1">{post.title}</h4>
                    <div className="text-[11px] text-muted-foreground mt-0.5">
                      Kênh {post.channel || "—"}
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
                    {post.status === "published" ? "Đã phát" : "Bản nháp"}
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
                Kênh {selectedPost.channel || "—"} • Xuất bản lúc {selectedPost.time} ngày {selectedPost.dateStr}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 pt-2">
              <div className="relative aspect-[16/9] rounded-xl overflow-hidden bg-black/80">
                <div className="size-full flex items-center justify-center text-white/70"><Film className="size-8" aria-hidden="true" /></div>
              </div>

              <div className="space-y-1.5 text-xs">
                <span className="font-bold text-foreground text-sm block">{selectedPost.title}</span>
                <p className="text-muted-foreground leading-relaxed text-xs">
                  Mã bài đăng: {selectedPost.externalPostId || "—"}
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

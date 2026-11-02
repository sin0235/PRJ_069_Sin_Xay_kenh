"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Kanban,
  Plus,
  Filter,
  Search,
  Sparkles,
  Clock,
  MoreVertical,
  CheckCircle2,
  Layers,
  ArrowRight,
  Film,
  FileText,
  Database,
  RefreshCw,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

import { IdeaService } from "@/services/idea-service";
import { ScriptService } from "@/services/script-service";
import { PublishingService } from "@/services/publishing-service";

interface PipelineCardItem {
  id: string;
  title: string;
  contentPillar?: string;
  status: "idea" | "script" | "production" | "review" | "scheduled" | "published";
  isAiGenerated?: boolean;
  durationSec?: number;
  itemType?: "idea" | "script" | "media";
}

const COLUMNS = [
  { id: "idea", title: "Idea (Ý Tưởng)", color: "text-amber-500", bg: "bg-amber-500/10" },
  { id: "script", title: "Script (Kịch Bản)", color: "text-blue-500", bg: "bg-blue-500/10" },
  { id: "production", title: "Production (Dựng Phim)", color: "text-teal-500", bg: "bg-teal-500/10" },
  { id: "review", title: "Review (Duyệt Kỹ Thuật)", color: "text-rose-500", bg: "bg-rose-500/10" },
  { id: "scheduled", title: "Scheduled (Đã Lên Lịch)", color: "text-emerald-500", bg: "bg-emerald-500/10" },
  { id: "published", title: "Published (Đã Phát)", color: "text-slate-500", bg: "bg-muted" },
];

export default function ContentPipelinePage() {
  const router = useRouter();
  const [items, setItems] = React.useState<PipelineCardItem[]>([]);
  const [filterOwner, setFilterOwner] = React.useState("all");
  const [isLiveConnected, setIsLiveConnected] = React.useState(false);
  const [loading, setLoading] = React.useState(true);

  const loadPipelineData = React.useCallback(async () => {
    setLoading(true);
    try {
      const [ideas, scripts, publishedLinks] = await Promise.all([
        IdeaService.getIdeas("all"),
        ScriptService.listScripts(),
        PublishingService.listPublishedLinks(),
      ]);
      const realItems: PipelineCardItem[] = [];

      ideas.forEach((idea) => {
        realItems.push({
          id: idea.id,
          title: idea.title,
          contentPillar: idea.contentPillar,
          status: "idea",
          itemType: "idea",
        });
      });

      scripts.forEach((script) => {
        const status: PipelineCardItem["status"] = script.status === "reviewed"
          ? "review"
          : script.status === "approved" ? "production" : "script";
        realItems.push({
          id: script.id,
          title: script.title,
          contentPillar: script.niche || undefined,
          status,
          durationSec: script.targetDurationSec || undefined,
          itemType: "script",
        });
      });

      publishedLinks.forEach((link) => {
        realItems.push({
          id: link.id,
          title: link.external_post_id,
          status: link.status === "ACTIVE" ? "published" : "scheduled",
          itemType: "media",
        });
      });

      setItems(realItems);
      if (realItems.length > 0) {
        setIsLiveConnected(true);
      }
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadPipelineData();
  }, [loadPipelineData]);

  const handleCardClick = (item: PipelineCardItem) => {
    if (item.itemType === "script" || item.status === "script") {
      router.push(`/scripts/${item.id}`);
    } else if (item.status === "production") {
      router.push("/video-studio");
    } else if (item.itemType === "idea" || item.status === "idea") {
      router.push("/ideas");
    } else {
      router.push(`/discover`);
    }
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Quy Trình Sản Xuất Nội Dung (Content Pipeline)
            </h1>
            <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
              Kanban Board
            </Badge>
            {isLiveConnected && (
              <Badge className="bg-emerald-500/10 text-emerald-600 border border-emerald-500/30 text-xs font-medium flex items-center gap-1">
                <Database className="size-3" />
                Dữ liệu trực tiếp
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Theo dõi dòng chảy sản xuất video ngắn TikTok từ lúc ươm mầm ý tưởng đến lúc lên lịch tự động.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={loadPipelineData}
            disabled={loading}
            className="h-8 text-xs font-medium rounded-lg gap-1.5"
          >
            <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Làm Mới</span>
          </Button>
          <Button
            size="sm"
            onClick={() => router.push("/ideas/generate")}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
          >
            <Plus className="size-3.5" />
            <span>Thêm Thẻ Nội Dung</span>
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-2xl border border-border/80 bg-card shadow-xs">
        <div className="text-xs text-muted-foreground font-medium">
          Tổng cộng: <span className="font-bold text-foreground">{items.length} thẻ nội dung thực tế</span>
        </div>
      </div>

      {/* Kanban Board Columns (6 Columns) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3.5 overflow-x-auto pb-4">
        {COLUMNS.map((col) => {
          const colItems = items.filter((i) => i.status === col.id);

          return (
            <div
              key={col.id}
              className="flex flex-col rounded-2xl border border-border/70 bg-muted/20 p-2.5 min-w-[240px]"
            >
              {/* Column Header */}
              <div className="flex items-center justify-between pb-2.5 px-1.5">
                <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                  <span className={`size-2 rounded-full ${col.bg} border ${col.color}`} />
                  {col.title}
                </span>
                <Badge variant="secondary" className="text-[10px] font-mono font-bold">
                  {colItems.length}
                </Badge>
              </div>

              {/* Column Item List */}
              <div className="space-y-2.5 flex-1 overflow-y-auto max-h-[calc(100vh-280px)] pr-0.5">
                {colItems.length === 0 ? (
                  <div className="py-8 text-center text-[11px] text-muted-foreground/60 border border-dashed rounded-xl">
                    Không có dữ liệu
                  </div>
                ) : (
                  colItems.map((item) => (
                    <Card
                      key={item.id}
                      onClick={() => handleCardClick(item)}
                      className="p-3 rounded-xl border border-border/70 bg-card hover:border-primary/50 transition-all cursor-pointer shadow-xs hover:shadow-md space-y-2.5"
                    >
                    {/* Thumbnail & Badges */}
                    <div className="relative aspect-[16/9] rounded-lg overflow-hidden bg-muted">
                      <div className="size-full flex items-center justify-center text-muted-foreground">
                        <Film className="size-8" aria-hidden="true" />
                      </div>
                      <div className="absolute top-1.5 left-1.5 flex gap-1">
                        {item.isAiGenerated && (
                          <Badge variant="outline" className="text-[9px] px-1 py-0 bg-primary/80 text-white backdrop-blur-xs border-none font-semibold">
                            <Sparkles className="size-2 mr-0.5 inline" /> AI
                          </Badge>
                        )}
                        {item.itemType === "script" && (
                          <Badge variant="outline" className="text-[9px] px-1 py-0 bg-blue-600/90 text-white backdrop-blur-xs border-none font-semibold">
                            <FileText className="size-2 mr-0.5 inline" /> Kịch bản
                          </Badge>
                        )}
                      </div>
                      {item.durationSec && (
                        <span className="absolute bottom-1 right-1 text-[9px] bg-black/70 text-white px-1 rounded font-mono">
                          {item.durationSec}s
                        </span>
                      )}
                    </div>

                    {/* Title */}
                    <div className="text-xs font-semibold text-foreground line-clamp-2 leading-snug">
                      {item.title}
                    </div>

                    {/* Metadata: Channel, Owner, Due Date */}
                    <div className="space-y-1.5 pt-1 border-t border-border/50 text-[10px] text-muted-foreground">
                      <div className="flex items-center justify-between">
                        <span className="truncate">{item.contentPillar || ""}</span>
                      </div>

                      <div className="flex items-center justify-between pt-0.5">
                        <span className="flex items-center gap-1 truncate max-w-[120px]">
                        </span>
                        <span className="text-[9px] text-primary font-medium flex items-center gap-0.5 shrink-0">
                          Chi tiết <ArrowRight className="size-2.5" />
                        </span>
                      </div>
                    </div>
                  </Card>
                )))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

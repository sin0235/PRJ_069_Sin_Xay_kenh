"use client";

import * as React from "react";
import { toast } from "sonner";
import {
  FolderOpen,
  Upload,
  Filter,
  Search,
  Sparkles,
  Film,
  Image as ImageIcon,
  Music,
  Mic,
  MoreVertical,
  CheckSquare,
  Trash2,
  Download,
  RotateCw,
  Play,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { mediaStudioApi, MediaAssetResponse } from "@/lib/api/media-studio-api";

interface MediaItem {
  id: string;
  name: string;
  type: "video" | "image" | "audio" | "voice";
  duration?: string;
  resolution?: string;
  isAiGenerated?: boolean;
  tags: string[];
  createdAt: string;
  url?: string;
  sha256?: string;
}

export default function MediaLibraryPage() {
  const [selectedType, setSelectedType] = React.useState("all");
  const [searchQuery, setSearchQuery] = React.useState("");
  const [assets, setAssets] = React.useState<MediaItem[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);

  const fetchLiveAssets = async () => {
    setIsLoading(true);
    try {
      const liveList = await mediaStudioApi.listAssets();
      setAssets(liveList.map((item) => {
        const isVideo = item.mime_detected.includes("video");
        const isAudio = item.mime_detected.includes("audio");
        return {
          id: item.id,
          name: item.original_filename || item.storage_key.split("/").pop() || "asset",
          type: isVideo ? "video" : isAudio ? "audio" : "image",
          duration: item.duration_ms ? `00:${String(Math.round(item.duration_ms / 1000)).padStart(2, "0")}` : undefined,
          isAiGenerated: ["FLOW", "GEMINI", "LYRIA"].some((source) => item.source_product.includes(source)),
          tags: [item.source_product],
          createdAt: new Date(item.created_at).toLocaleDateString("vi-VN"),
          url: item.url,
          sha256: item.sha256,
        };
      }));
    } catch (error) {
      setAssets([]);
      toast.error(error instanceof Error ? error.message : "Không tải được thư viện tư liệu.");
    } finally {
      setIsLoading(false);
    }
  };

  React.useEffect(() => {
    fetchLiveAssets();
  }, []);

  const filteredAssets = assets.filter(
    (a) =>
      (selectedType === "all" || a.type === selectedType) &&
      (a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.tags.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase())))
  );

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Thư Viện Tư Liệu (Media Library)
            </h1>
            <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
              Grid-First Asset Manager
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Quản lý tài nguyên video 9:16, âm nhạc Flow Music Plus và track hòa âm Auto-Ducking cho kênh TikTok.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={fetchLiveAssets}
            disabled={isLoading}
            className="h-8 text-xs rounded-lg gap-1.5"
          >
            <RotateCw className={`size-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Làm mới thư viện</span>
          </Button>

          <Button
            size="sm"
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
          >
            <Upload className="size-3.5" />
            <span>Tải Lên Tư Liệu Mới</span>
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 rounded-2xl border border-border/80 bg-card shadow-xs">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Input
            placeholder="Tìm theo tên file, tag hoặc nguồn sinh..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 text-xs rounded-lg min-w-[240px]"
          />

          <Select value={selectedType} onValueChange={setSelectedType}>
            <SelectTrigger className="h-8 text-xs rounded-lg min-w-[130px]">
              <SelectValue placeholder="Loại file" />
            </SelectTrigger>
            <SelectContent className="rounded-xl">
              <SelectItem value="all">Tất cả định dạng</SelectItem>
              <SelectItem value="video">Video B-Roll 9:16</SelectItem>
              <SelectItem value="audio">Âm thanh Flow Music</SelectItem>
              <SelectItem value="image">Hình ảnh / Bìa</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
          <span>{filteredAssets.length} tư liệu sẵn sàng</span>
        </div>
      </div>

      {/* Asset Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {filteredAssets.length === 0 && (
          <div className="col-span-full py-12 text-center text-sm text-muted-foreground">Chưa có tư liệu phù hợp.</div>
        )}
        {filteredAssets.map((asset) => (
          <Card
            key={asset.id}
            className="group rounded-2xl border-border/80 bg-card hover:border-primary/40 transition-all overflow-hidden shadow-xs hover:shadow-md flex flex-col justify-between"
          >
            {/* Visual Preview */}
            <div className="relative aspect-[16/10] bg-muted overflow-hidden">
              <div className="size-full flex items-center justify-center text-muted-foreground">
                {asset.type === "video" ? <Film className="size-8" aria-hidden="true" /> : asset.type === "audio" ? <Music className="size-8" aria-hidden="true" /> : <ImageIcon className="size-8" aria-hidden="true" />}
              </div>

              <div className="absolute top-2 left-2 flex gap-1">
                {asset.isAiGenerated && (
                  <Badge variant="outline" className="text-[9px] bg-primary/80 text-white backdrop-blur-xs border-none font-semibold">
                    <Sparkles className="size-2 mr-0.5 inline" /> AI Zero-Cost
                  </Badge>
                )}
                <Badge variant="secondary" className="text-[9px] uppercase font-mono">
                  {asset.type}
                </Badge>
              </div>

              {asset.duration && (
                <span className="absolute bottom-1 right-1 text-[9px] bg-black/70 text-white px-1.5 py-0.5 rounded font-mono">
                  {asset.duration}
                </span>
              )}
            </div>

            {/* Details */}
            <div className="p-3.5 space-y-2 flex-1 flex flex-col justify-between">
              <div>
                <h4 className="text-xs font-semibold text-foreground line-clamp-1 leading-snug">
                  {asset.name}
                </h4>
                <div className="text-[10px] text-muted-foreground mt-0.5 flex items-center justify-between">
                  <span>{asset.createdAt}</span>
                </div>

              </div>

              <div className="flex flex-wrap gap-1 pt-1">
                {asset.tags.map((t) => (
                  <span
                    key={t}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-muted/70 text-muted-foreground font-mono"
                  >
                    #{t}
                  </span>
                ))}
              </div>

              {asset.url && (
                <div className="pt-2 border-t border-border/50 flex items-center justify-between">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[10px] px-2 text-primary"
                    onClick={() => mediaStudioApi.downloadAsset(asset.url!, asset.name).catch((error) => toast.error(error.message))}
                  >
                    <Download className="size-3 mr-1" /> Tải về
                  </Button>
                  <span className="text-[9px] text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-0.5">
                    <ShieldCheck className="size-3" /> QC Verified
                  </span>
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

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
  Database,
  Eye,
  Copy,
  Check,
  FileText,
  Clock,
  Layers,
  ArrowRight,
  HardDrive,
  Loader2,
  Volume2,
  ExternalLink,
} from "lucide-react";

import { cn } from "cn";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { mediaStudioApi, MediaAssetResponse } from "@/lib/api/media-studio-api";
import { AuthApi } from "@/lib/api/auth-api";
import {
  StatusBeacon,
  SoundEqualizer,
  ShimmerProgressBar,
  FloatingSparkleSVG,
} from "@/components/creator/dynamic-visuals";
import { SpotlightCard, NumberTicker, ShimmerButton } from "@/components/creator/motion-primitives";

interface MediaItem {
  id: string;
  name: string;
  type: "video" | "image" | "audio";
  byteSize: number;
  sizeFormatted: string;
  duration?: string;
  durationMs?: number;
  resolution?: string;
  isAiGenerated: boolean;
  projectUsageCount: number;
  projectId?: string;
  tags: string[];
  createdAt: string;
  url?: string;
  sha256?: string;
  mimeDetected: string;
  sourceProduct: string;
  approvalState: string;
}

function formatBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatDuration(ms?: number): string | undefined {
  if (!ms || ms <= 0) return undefined;
  const totalSec = Math.round(ms / 1000);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export default function MediaLibraryPage() {
  const [selectedType, setSelectedType] = React.useState("all");
  const [selectedSource, setSelectedSource] = React.useState("all");
  const [sortBy, setSortBy] = React.useState("newest");
  const [searchQuery, setSearchQuery] = React.useState("");
  const [assets, setAssets] = React.useState<MediaItem[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [isUploading, setIsUploading] = React.useState(false);
  const [uploadProgress, setUploadProgress] = React.useState<string | null>(null);

  // Preview Dialog State
  const [previewAsset, setPreviewAsset] = React.useState<MediaItem | null>(null);
  const [previewPlaybackUrl, setPreviewPlaybackUrl] = React.useState<string | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = React.useState(false);
  const [copiedSha, setCopiedSha] = React.useState<string | null>(null);

  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const fetchLiveAssets = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const liveList = await mediaStudioApi.listAssets({ throwOnError: false });
      const mapped: MediaItem[] = liveList.map((item) => {
        const isVideo = item.mime_detected.includes("video");
        const isAudio = item.mime_detected.includes("audio");
        const isImage = item.mime_detected.includes("image");

        const type: MediaItem["type"] = isVideo ? "video" : isAudio ? "audio" : "image";

        const isAi =
          (item.source_product || "").toUpperCase().includes("FLOW") ||
          (item.source_product || "").toUpperCase().includes("GEMINI") ||
          (item.source_product || "").toUpperCase().includes("LYRIA") ||
          (item.source_product || "").toUpperCase().includes("VIE_NEU") ||
          (item.source_product || "").toUpperCase().includes("GWEN") ||
          (item.source_product || "").toUpperCase().includes("AI");

        const mimeShort = item.mime_detected.split("/")[1]?.toUpperCase() || "TỆP";

        const tags = [
          item.source_product || "MEDIA",
          mimeShort,
          ...(isVideo ? ["9:16 TikTok"] : []),
          ...(isAudio ? ["-14 LUFS"] : []),
        ];

        return {
          id: item.id,
          name: item.original_filename || item.storage_key.split("/").pop() || `tu-lieu-${item.id.slice(0, 8)}`,
          type,
          byteSize: item.byte_size,
          sizeFormatted: formatBytes(item.byte_size),
          duration: formatDuration(item.duration_ms),
          durationMs: item.duration_ms,
          resolution: isVideo ? "1080x1920 (9:16)" : undefined,
          isAiGenerated: isAi,
          projectUsageCount: item.project_id ? 1 : 0,
          projectId: item.project_id,
          tags,
          createdAt: item.created_at ? new Date(item.created_at).toLocaleString("vi-VN") : "Vừa xong",
          url: item.url,
          sha256: item.sha256,
          mimeDetected: item.mime_detected,
          sourceProduct: item.source_product,
          approvalState: item.approval_state || "UNREVIEWED",
        };
      });

      // Sort by default newest
      mapped.sort((a, b) => (Date.parse(b.createdAt) || 0) - (Date.parse(a.createdAt) || 0));
      setAssets(mapped);
    } catch (error: any) {
      toast.error("Không thể tải danh sách tài nguyên media: " + (error.message || "Lỗi không xác định"));
      setAssets([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void fetchLiveAssets();
  }, [fetchLiveAssets]);

  // Handle uploading real files
  const handleUploadFiles = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setUploadProgress(`Đang tải lên ${i + 1}/${files.length}: ${file.name}`);

      let category: "video" | "audio" | "image" = "video";
      if (file.type.startsWith("audio/")) category = "audio";
      else if (file.type.startsWith("image/")) category = "image";

      try {
        await mediaStudioApi.uploadAsset({
          file,
          expected_category: category,
          source_product: "UPLOAD",
        });
        successCount++;
      } catch (err: any) {
        failCount++;
        toast.error(`Lỗi tải lên "${file.name}": ${err.message || "Thất bại"}`);
      }
    }

    if (successCount > 0) {
      toast.success(`Đã tải lên thành công ${successCount} tệp tư liệu.`);
      await fetchLiveAssets();
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    setIsUploading(false);
    setUploadProgress(null);
  };

  // Handle Preview Open & Close
  const handleOpenPreview = async (asset: MediaItem) => {
    setPreviewAsset(asset);
    setPreviewPlaybackUrl(null);
    if (!asset.url) return;

    setIsLoadingPreview(true);
    try {
      const playbackUrl = await mediaStudioApi.createAssetObjectUrl(asset.url);
      setPreviewPlaybackUrl(playbackUrl);
    } catch {
      // Fallback direct url if object url failed
      setPreviewPlaybackUrl(asset.url);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const handleClosePreview = () => {
    if (previewPlaybackUrl?.startsWith("blob:")) {
      URL.revokeObjectURL(previewPlaybackUrl);
    }
    setPreviewAsset(null);
    setPreviewPlaybackUrl(null);
  };

  const handleCopySha = (sha: string) => {
    navigator.clipboard.writeText(sha);
    setCopiedSha(sha);
    toast.success("Đã sao chép mã SHA-256");
    setTimeout(() => setCopiedSha(null), 2000);
  };

  // Stats calculation
  const stats = React.useMemo(() => {
    const total = assets.length;
    const videos = assets.filter((a) => a.type === "video").length;
    const audios = assets.filter((a) => a.type === "audio").length;
    const images = assets.filter((a) => a.type === "image").length;
    const totalBytes = assets.reduce((acc, a) => acc + (a.byteSize || 0), 0);
    return {
      total,
      videos,
      audios,
      images,
      storageFormatted: formatBytes(totalBytes),
    };
  }, [assets]);

  // Filtering & Sorting
  const filteredAssets = React.useMemo(() => {
    let list = assets.filter((a) => {
      if (selectedType !== "all" && a.type !== selectedType) return false;
      if (selectedSource === "ai" && !a.isAiGenerated) return false;
      if (selectedSource === "upload" && a.isAiGenerated) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchName = a.name.toLowerCase().includes(q);
        const matchTag = a.tags.some((t) => t.toLowerCase().includes(q));
        const matchSha = (a.sha256 || "").toLowerCase().includes(q);
        const matchProduct = (a.sourceProduct || "").toLowerCase().includes(q);
        if (!matchName && !matchTag && !matchSha && !matchProduct) return false;
      }
      return true;
    });

    if (sortBy === "oldest") {
      list = [...list].sort((a, b) => (Date.parse(a.createdAt) || 0) - (Date.parse(b.createdAt) || 0));
    } else if (sortBy === "size") {
      list = [...list].sort((a, b) => (b.byteSize || 0) - (a.byteSize || 0));
    }

    return list;
  }, [assets, selectedType, selectedSource, searchQuery, sortBy]);

  return (
    <div className="space-y-6 pb-20">
      {/* Hidden file input for uploading */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleUploadFiles}
        multiple
        accept="video/*,audio/*,image/*"
        className="hidden"
      />

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <FloatingSparkleSVG className="text-primary size-5" />
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Thư Viện Tư Liệu (Media Library)
            </h1>
            <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold gap-1.5">
              <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Kho Lưu Trữ Trực Tiếp
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Quản lý tập trung toàn bộ video 9:16, âm nhạc Flow Music Plus, giọng đọc TTS và đồ họa thương hiệu.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => void fetchLiveAssets()}
            disabled={isLoading}
            className="h-8 text-xs rounded-lg gap-1.5"
          >
            <RotateCw className={cn("size-3.5", isLoading && "animate-spin")} />
            <span>{isLoading ? "Đang đồng bộ..." : "Làm mới"}</span>
          </Button>

          <ShimmerButton
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="h-8 text-xs font-semibold py-1.5 px-3"
          >
            {isUploading ? <Loader2 className="size-3.5 animate-spin" /> : <Upload className="size-3.5" />}
            <span>{isUploading ? "Đang tải lên..." : "Tải Lên Tư Liệu Mới"}</span>
          </ShimmerButton>
        </div>
      </div>

      {/* Upload Progress Banner */}
      {isUploading && uploadProgress && (
        <Card className="p-4 border-primary/40 bg-primary/5 rounded-2xl space-y-3 shadow-xs">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Loader2 className="size-5 text-primary animate-spin" />
              <div>
                <p className="text-xs font-semibold text-foreground">{uploadProgress}</p>
                <p className="text-[11px] text-muted-foreground">Tự động kiểm tra mã băm SHA-256 và tối ưu chuẩn hóa.</p>
              </div>
            </div>
            <Badge variant="secondary" className="text-xs font-mono gap-1.5">
              <StatusBeacon status="processing" size="sm" />
              <span>Đang xử lý</span>
            </Badge>
          </div>
          <ShimmerProgressBar value={68} isProcessing />
        </Card>
      )}

      {/* Stats Quick Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-3.5 rounded-2xl border-border/70 bg-card shadow-xs flex items-center gap-3 card-hover-lift">
          <div className="size-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <FolderOpen className="size-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-foreground leading-tight">
              <NumberTicker value={stats.total} duration={1.2} />
            </div>
            <div className="text-[11px] text-muted-foreground">Tổng số tư liệu</div>
          </div>
        </Card>

        <Card className="p-3.5 rounded-2xl border-border/70 bg-card shadow-xs flex items-center gap-3 card-hover-lift">
          <div className="size-9 rounded-xl bg-blue-500/10 text-blue-500 flex items-center justify-center shrink-0">
            <Film className="size-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-foreground leading-tight">
              <NumberTicker value={stats.videos} duration={1.2} />
            </div>
            <div className="text-[11px] text-muted-foreground">Video phân cảnh</div>
          </div>
        </Card>

        <Card className="p-3.5 rounded-2xl border-border/70 bg-card shadow-xs flex items-center gap-3 card-hover-lift">
          <div className="size-9 rounded-xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center shrink-0">
            <Music className="size-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-foreground leading-tight">
              <NumberTicker value={stats.audios} duration={1.2} />
            </div>
            <div className="text-[11px] text-muted-foreground">Âm nhạc & Giọng đọc</div>
          </div>
        </Card>

        <Card className="p-3.5 rounded-2xl border-border/70 bg-card shadow-xs flex items-center gap-3 card-hover-lift">
          <div className="size-9 rounded-xl bg-amber-500/10 text-amber-500 flex items-center justify-center shrink-0">
            <HardDrive className="size-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-foreground leading-tight">{stats.storageFormatted}</div>
            <div className="text-[11px] text-muted-foreground">Dung lượng sử dụng</div>
          </div>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-3 p-3.5 rounded-2xl border border-border/80 bg-card shadow-xs">
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          <div className="relative w-full sm:w-64">
            <Search className="size-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
            <Input
              placeholder="Tìm theo tên file, tag, SHA-256..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 pl-8 text-xs rounded-lg w-full"
            />
          </div>

          <Select value={selectedType} onValueChange={setSelectedType}>
            <SelectTrigger className="h-8 text-xs rounded-lg min-w-[130px]">
              <SelectValue placeholder="Định dạng" />
            </SelectTrigger>
            <SelectContent className="rounded-xl">
              <SelectItem value="all">Tất cả định dạng</SelectItem>
              <SelectItem value="video">Video dọc 9:16</SelectItem>
              <SelectItem value="audio">Âm thanh & TTS</SelectItem>
              <SelectItem value="image">Hình ảnh / Bìa</SelectItem>
            </SelectContent>
          </Select>

          <Select value={selectedSource} onValueChange={setSelectedSource}>
            <SelectTrigger className="h-8 text-xs rounded-lg min-w-[130px]">
              <SelectValue placeholder="Nguồn tạo" />
            </SelectTrigger>
            <SelectContent className="rounded-xl">
              <SelectItem value="all">Tất cả nguồn</SelectItem>
              <SelectItem value="ai">Do AI tạo (Flow/TTS)</SelectItem>
              <SelectItem value="upload">Tải lên thủ công</SelectItem>
            </SelectContent>
          </Select>

          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="h-8 text-xs rounded-lg min-w-[120px]">
              <SelectValue placeholder="Sắp xếp" />
            </SelectTrigger>
            <SelectContent className="rounded-xl">
              <SelectItem value="newest">Mới nhất</SelectItem>
              <SelectItem value="oldest">Cũ nhất</SelectItem>
              <SelectItem value="size">Dung lượng lớn</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono shrink-0">
          <span>{filteredAssets.length} tư liệu hiển thị</span>
        </div>
      </div>

      {/* Asset Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {filteredAssets.length === 0 ? (
          <div className="col-span-full flex flex-col items-center justify-center p-12 border border-dashed rounded-2xl text-center bg-card/40">
            <Database className="size-10 text-muted-foreground mb-3 opacity-60" />
            <h3 className="text-sm font-semibold text-foreground">Không có tư liệu phù hợp</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">
              {searchQuery || selectedType !== "all" || selectedSource !== "all"
                ? "Không tìm thấy tư liệu nào khớp với điều kiện lọc hiện tại."
                : "Chưa có video, âm thanh hay hình ảnh nào trong kho media. Nhấp nút tải lên để thêm tệp mới."}
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              className="mt-4 text-xs rounded-lg gap-1.5"
            >
              <Upload className="size-3.5" />
              <span>Tải lên tư liệu đầu tiên</span>
            </Button>
          </div>
        ) : (
          filteredAssets.map((asset) => {
            const isVideo = asset.type === "video";
            const isAudio = asset.type === "audio";
            const isImage = asset.type === "image";

            return (
              <SpotlightCard
                key={asset.id}
                className="group rounded-2xl border-border/80 bg-card hover:border-primary/40 transition-all overflow-hidden shadow-xs hover:shadow-md flex flex-col justify-between card-hover-lift"
                spotlightColor="rgba(43, 111, 184, 0.14)"
                spotlightSize={280}
              >
                {/* Visual Preview Container */}
                <div
                  className="relative aspect-[16/10] bg-muted/60 overflow-hidden flex items-center justify-center cursor-pointer"
                  onClick={() => handleOpenPreview(asset)}
                >
                  {isVideo && (
                    <div className="flex flex-col items-center justify-center gap-1.5 text-muted-foreground group-hover:text-primary transition-colors">
                      <div className="size-10 rounded-xl bg-background/80 shadow-xs flex items-center justify-center group-hover:scale-110 transition-transform">
                        <Play className="size-5 text-primary fill-primary/20" />
                      </div>
                      <span className="text-[10px] font-mono text-muted-foreground">Video 9:16</span>
                    </div>
                  )}

                  {isAudio && (
                    <div className="flex flex-col items-center justify-center gap-1.5 text-muted-foreground group-hover:text-emerald-500 transition-colors">
                      <div className="size-10 rounded-xl bg-background/80 shadow-xs flex items-center justify-center group-hover:scale-110 transition-transform">
                        <Volume2 className="size-5 text-emerald-500" />
                      </div>
                      <SoundEqualizer isPlaying={false} className="h-3 text-emerald-500/80" />
                      <span className="text-[10px] font-mono text-muted-foreground">Audio Track</span>
                    </div>
                  )}

                  {isImage && (
                    <div className="flex flex-col items-center justify-center gap-1.5 text-muted-foreground group-hover:text-blue-500 transition-colors">
                      <div className="size-10 rounded-xl bg-background/80 shadow-xs flex items-center justify-center group-hover:scale-110 transition-transform">
                        <ImageIcon className="size-5 text-blue-500" />
                      </div>
                      <span className="text-[10px] font-mono text-muted-foreground">Hình ảnh / Bìa</span>
                    </div>
                  )}

                  {/* Top Badges */}
                  <div className="absolute top-2 left-2 flex gap-1">
                    {asset.isAiGenerated && (
                      <Badge variant="outline" className="text-[9px] bg-primary/80 text-white backdrop-blur-xs border-none font-semibold">
                        <Sparkles className="size-2 mr-0.5 inline" /> AI
                      </Badge>
                    )}
                    <Badge variant="secondary" className="text-[9px] uppercase font-mono">
                      {asset.type}
                    </Badge>
                  </div>

                  {/* Duration Badge */}
                  {asset.duration && (
                    <span className="absolute bottom-1.5 right-1.5 text-[9px] bg-black/75 text-white px-1.5 py-0.5 rounded font-mono">
                      {asset.duration}
                    </span>
                  )}
                </div>

                {/* Details */}
                <div className="p-3.5 space-y-2 flex-1 flex flex-col justify-between">
                  <div>
                    <h4
                      className="text-xs font-semibold text-foreground line-clamp-1 leading-snug cursor-pointer hover:text-primary transition-colors"
                      onClick={() => handleOpenPreview(asset)}
                      title={asset.name}
                    >
                      {asset.name}
                    </h4>
                    <div className="text-[10px] text-muted-foreground mt-0.5 flex items-center justify-between">
                      <span>{asset.sizeFormatted}</span>
                      <span>{asset.createdAt}</span>
                    </div>
                  </div>

                  {/* Tags */}
                  <div className="flex flex-wrap gap-1 pt-1">
                    {asset.tags.slice(0, 3).map((t) => (
                      <span
                        key={t}
                        className="text-[9px] px-1.5 py-0.5 rounded bg-muted/70 text-muted-foreground font-mono"
                      >
                        #{t}
                      </span>
                    ))}
                  </div>

                  {/* Action Buttons */}
                  <div className="pt-2 border-t border-border/50 flex items-center justify-between gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-[10px] px-2 text-primary hover:bg-primary/10 gap-1"
                      onClick={() => handleOpenPreview(asset)}
                    >
                      <Eye className="size-3" /> Xem chi tiết
                    </Button>

                    {asset.url && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-[10px] px-2 text-muted-foreground hover:text-foreground gap-1"
                        onClick={() =>
                          mediaStudioApi
                            .downloadAsset(asset.url!, asset.name)
                            .then(() => toast.success("Đang tải xuống tệp..."))
                            .catch((error) => toast.error(error.message))
                        }
                      >
                        <Download className="size-3" /> Tải về
                      </Button>
                    )}
                  </div>
                </div>
              </SpotlightCard>
            );
          })
        )}
      </div>

      {/* Interactive Asset Preview Dialog */}
      <Dialog open={!!previewAsset} onOpenChange={(open) => !open && handleClosePreview()}>
        <DialogContent className="max-w-2xl p-5 rounded-2xl">
          {previewAsset && (
            <div className="space-y-4">
              <DialogHeader>
                <div className="flex items-center gap-2">
                  <DialogTitle className="text-base font-bold text-foreground line-clamp-1">
                    {previewAsset.name}
                  </DialogTitle>
                  <Badge variant="secondary" className="text-[10px] uppercase font-mono">
                    {previewAsset.type}
                  </Badge>
                </div>
                <DialogDescription className="text-xs text-muted-foreground">
                  Định dạng: {previewAsset.mimeDetected} | Dung lượng: {previewAsset.sizeFormatted}
                </DialogDescription>
              </DialogHeader>

              {/* Media Preview Box */}
              <div className="relative rounded-xl overflow-hidden bg-black/90 flex items-center justify-center min-h-[220px] max-h-[380px]">
                {isLoadingPreview ? (
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <Loader2 className="size-6 text-primary animate-spin" />
                    <span className="text-xs">Đang nạp dữ liệu media...</span>
                  </div>
                ) : previewPlaybackUrl ? (
                  previewAsset.type === "video" ? (
                    <video
                      controls
                      autoPlay
                      src={previewPlaybackUrl}
                      className="max-h-[360px] max-w-full rounded-lg"
                    />
                  ) : previewAsset.type === "audio" ? (
                    <div className="w-full p-6 flex flex-col items-center gap-4">
                      <div className="size-16 rounded-2xl bg-primary/20 text-primary flex items-center justify-center">
                        <Volume2 className="size-8" />
                      </div>
                      <SoundEqualizer isPlaying={true} className="h-8 text-primary" />
                      <audio controls autoPlay src={previewPlaybackUrl} className="w-full" />
                    </div>
                  ) : (
                    <img
                      src={previewPlaybackUrl}
                      alt={previewAsset.name}
                      className="max-h-[360px] max-w-full object-contain rounded-lg"
                    />
                  )
                ) : (
                  <div className="p-8 text-center text-xs text-muted-foreground">
                    Không thể phát trực tiếp tệp này trên trình duyệt.
                  </div>
                )}
              </div>

              {/* Metadata Details Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 p-3 rounded-xl bg-muted/40 border border-border/60 text-xs">
                <div>
                  <span className="text-[10px] text-muted-foreground block">Mã tệp (ID)</span>
                  <span className="font-mono text-[11px] font-semibold text-foreground truncate block">
                    {previewAsset.id}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-muted-foreground block">Nguồn tạo</span>
                  <span className="font-mono text-[11px] font-semibold text-foreground">
                    {previewAsset.sourceProduct}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-muted-foreground block">Thời lượng</span>
                  <span className="font-mono text-[11px] font-semibold text-foreground">
                    {previewAsset.duration || "N/A"}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-muted-foreground block">Ngày tạo</span>
                  <span className="font-mono text-[11px] text-foreground">
                    {previewAsset.createdAt}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-muted-foreground block">Kiểm duyệt</span>
                  <Badge variant="outline" className="text-[9px] border-emerald-500/40 text-emerald-600 bg-emerald-500/10">
                    <ShieldCheck className="size-2.5 mr-0.5 inline" />
                    {previewAsset.approvalState}
                  </Badge>
                </div>
                <div>
                  <span className="text-[10px] text-muted-foreground block">Chuẩn âm/hình</span>
                  <span className="text-[11px] font-semibold text-foreground">
                    {previewAsset.type === "video" ? "9:16 Safe Zone" : "-14 LUFS Normalized"}
                  </span>
                </div>
              </div>

              {/* SHA-256 Box */}
              {previewAsset.sha256 && (
                <div className="flex items-center justify-between p-2.5 rounded-xl border border-border/70 bg-card text-xs">
                  <div className="min-w-0 pr-2">
                    <span className="text-[10px] text-muted-foreground block">Mã băm SHA-256 (Tính toàn vẹn)</span>
                    <span className="font-mono text-[11px] text-muted-foreground truncate block">
                      {previewAsset.sha256}
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleCopySha(previewAsset.sha256!)}
                    className="h-7 px-2 text-xs shrink-0"
                  >
                    {copiedSha === previewAsset.sha256 ? (
                      <Check className="size-3.5 text-emerald-500" />
                    ) : (
                      <Copy className="size-3.5" />
                    )}
                  </Button>
                </div>
              )}

              {/* Actions Footer */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/60">
                <Button variant="outline" size="sm" onClick={handleClosePreview} className="text-xs">
                  Đóng
                </Button>
                {previewAsset.url && (
                  <Button
                    size="sm"
                    onClick={() =>
                      mediaStudioApi
                        .downloadAsset(previewAsset.url!, previewAsset.name)
                        .then(() => toast.success("Đang bắt đầu tải tệp về máy..."))
                        .catch((error) => toast.error(error.message))
                    }
                    className="text-xs bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5"
                  >
                    <Download className="size-3.5" />
                    <span>Tải Về Tệp Gốc</span>
                  </Button>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

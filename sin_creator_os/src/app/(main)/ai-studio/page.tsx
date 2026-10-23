"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  FileText,
  Flame,
  Type,
  Hash,
  Image as ImageIcon,
  Mic,
  Volume2,
  Film,
  Camera,
  Video,
  RotateCw,
  Clock,
  CheckCircle2,
  AlertCircle,
  Coins,
  ArrowRight,
  Music,
  Sliders,
  Play,
  Download,
  Loader2,
  ShieldCheck,
  Upload,
  Copy,
  Check,
  BookOpen,
  Wand2,
  Layers,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { mockAIJobs } from "@/data/mock-creator-data";
import { AIJob } from "@/types";
import { mediaStudioApi, MediaAssetResponse, CompiledVideoPromptResponse } from "@/lib/api/media-studio-api";

const AI_TOOLS = [
  {
    id: "tool_script",
    name: "Script Generator",
    description: "Sinh kịch bản 5 block tối ưu tỷ lệ xem hết dựa trên cấu trúc video viral",
    icon: FileText,
    badge: "Most Used",
    credits: 3,
    route: "/ideas/generate",
    category: "Writing",
  },
  {
    id: "tool_hook",
    name: "Viral Hook Generator",
    description: "Tạo 10 mẫu câu mở đầu 3 giây gây tò mò tâm lý cực mạnh kèm visual cue",
    icon: Flame,
    badge: "Retention",
    credits: 1,
    route: "/ideas",
    category: "Writing",
  },
  {
    id: "tool_caption",
    name: "Caption & CTA Optimizer",
    description: "Tối ưu mô tả bài đăng kích hoạt thuật toán đề xuất và comment tự động",
    icon: Type,
    badge: "Engagement",
    credits: 1,
    route: "/publishing",
    category: "Writing",
  },
  {
    id: "tool_hashtag",
    name: "Hashtag Intelligence",
    description: "Phân tích cụm hashtag ngách ít cạnh tranh có vận tốc tăng trưởng cao",
    icon: Hash,
    badge: "SEO",
    credits: 1,
    route: "/trends",
    category: "SEO",
  },
  {
    id: "tool_voice",
    name: "Voice Clone & TTS",
    description: "Tổng hợp giọng đọc truyền cảm chuẩn ngữ điệu TikTok tiếng Việt",
    icon: Mic,
    badge: "Audio AI",
    credits: 5,
    route: "/video-studio",
    category: "Audio",
  },
  {
    id: "tool_broll",
    name: "B-Roll Prompt Generator",
    description: "Gợi ý shot list và prompt sinh hình ảnh/video b-roll khớp từng nhịp thoại",
    icon: Film,
    badge: "Visual",
    credits: 2,
    route: "/media",
    category: "Visual",
  },
  {
    id: "tool_thumb",
    name: "TikTok Thumbnail Maker",
    description: "Tạo ảnh bìa 9:16 có text bôi đậm trong Safe Zone thu hút lượt click",
    icon: Camera,
    badge: "Design",
    credits: 4,
    route: "/media",
    category: "Visual",
  },
  {
    id: "tool_video",
    name: "Full AI Video Generator",
    description: "Dây chuyền tự động từ kịch bản → giọng đọc → ghép clip → phụ đề dọc",
    icon: Video,
    badge: "Autonomous",
    credits: 10,
    route: "/video-studio",
    category: "Video",
  },
];

export default function AIStudioPage() {
  const router = useRouter();
  const [selectedCategory, setSelectedCategory] = React.useState("all");
  const [jobs, setJobs] = React.useState<AIJob[]>(mockAIJobs);

  const handleRetry = (id: string) => {
    setJobs((prev) =>
      prev.map((j) => (j.id === id ? { ...j, status: "processing", progress: 20, error: undefined } : j))
    );
  };

  // States cho Interactive Generative Studio
  const [activeMediaTab, setActiveMediaTab] = React.useState<"music" | "video">("music");
  
  // Music State
  const [musicPrompt, setMusicPrompt] = React.useState("Giai điệu acoustic guitar nhẹ nhàng thư thái buổi sáng");
  const [musicGenre, setMusicGenre] = React.useState("Acoustic");
  const [musicMood, setMusicMood] = React.useState("Relaxing");
  const [musicProvider, setMusicProvider] = React.useState<"FLOW_BROWSER_PILOT" | "GOOGLE_OFFICIAL">("FLOW_BROWSER_PILOT");
  const [isGeneratingMusic, setIsGeneratingMusic] = React.useState(false);
  const [generatedMusic, setGeneratedMusic] = React.useState<MediaAssetResponse | null>(null);
  const [generatedMusicPlaybackUrl, setGeneratedMusicPlaybackUrl] = React.useState<string | null>(null);

  // Video State
  const [videoPrompt, setVideoPrompt] = React.useState("Cảnh quay cận cảnh ly cà phê sữa đá nhỏ giọt giọt dưới ánh nắng ban mai");
  const [isGeneratingVideo, setIsGeneratingVideo] = React.useState(false);
  const [generatedVideo, setGeneratedVideo] = React.useState<MediaAssetResponse | null>(null);
  const [generatedVideoPlaybackUrl, setGeneratedVideoPlaybackUrl] = React.useState<string | null>(null);
  // Prompt Compiler & image reference states
  const [compiledPrompt, setCompiledPrompt] = React.useState<CompiledVideoPromptResponse | null>(null);
  const [isCompiling, setIsCompiling] = React.useState(false);
  const [isUploadingReference, setIsUploadingReference] = React.useState(false);
  const [referenceImage, setReferenceImage] = React.useState<MediaAssetResponse | null>(null);
  const [copiedDirective, setCopiedDirective] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  // Toast / Error state
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [successMessage, setSuccessMessage] = React.useState<string | null>(null);
  const [isOpeningFlowLogin, setIsOpeningFlowLogin] = React.useState(false);

  const filteredTools = AI_TOOLS.filter(
    (t) => selectedCategory === "all" || t.category.toLowerCase() === selectedCategory.toLowerCase()
  );

  const handleGenerateMusic = async () => {
    setIsGeneratingMusic(true);
    setErrorMessage(null);
    const idempotencyKey = `music-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    const monitor = new AbortController();
    try {
      const params = {
        prompt: musicPrompt,
        genre: musicGenre,
        mood: musicMood,
        provider: musicProvider,
        use_official_lyria: musicProvider === "GOOGLE_OFFICIAL",
        idempotency_key: idempotencyKey,
        normalize_tiktok: true,
      };
      const res = await Promise.race([
        mediaStudioApi.generateMusic(params),
        mediaStudioApi.waitForMusicResult(idempotencyKey, monitor.signal),
      ]);
      const playbackUrl = await mediaStudioApi.createAssetObjectUrl(res.url || "");
      setGeneratedMusic(res);
      setGeneratedMusicPlaybackUrl(playbackUrl);
    } catch (err: any) {
      setErrorMessage(err.message || "Không thể tạo nhạc");
    } finally {
      monitor.abort();
      setIsGeneratingMusic(false);
    }
  };

  React.useEffect(() => {
    const playbackUrl = generatedMusicPlaybackUrl;
    return () => {
      if (playbackUrl?.startsWith("blob:")) URL.revokeObjectURL(playbackUrl);
    };
  }, [generatedMusicPlaybackUrl]);

  React.useEffect(() => {
    const playbackUrl = generatedVideoPlaybackUrl;
    return () => {
      if (playbackUrl?.startsWith("blob:")) URL.revokeObjectURL(playbackUrl);
    };
  }, [generatedVideoPlaybackUrl]);

  React.useEffect(() => {
    let cancelled = false;
    void mediaStudioApi.listAssets().then(async (assets) => {
      const latestVideo = assets
        .filter((asset) => asset.mime_detected.startsWith("video/") && asset.source_product === "GOOGLE_FLOW")
        .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0];
      if (!latestVideo?.url) return;

      const playbackUrl = await mediaStudioApi.createAssetObjectUrl(latestVideo.url);
      if (cancelled) {
        URL.revokeObjectURL(playbackUrl);
        return;
      }
      setGeneratedVideo(latestVideo);
      setGeneratedVideoPlaybackUrl(playbackUrl);
    }).catch((err: unknown) => {
      if (!cancelled) setErrorMessage(err instanceof Error ? err.message : "Không tải được video Flow đã tạo.");
    });
    return () => { cancelled = true; };
  }, []);

  const handleDownloadAsset = async (asset: MediaAssetResponse) => {
    if (!asset.url) return;
    try {
      await mediaStudioApi.downloadAsset(asset.url, asset.original_filename || "media");
    } catch (err: any) {
      setErrorMessage(err.message || "Không thể tải tệp media.");
    }
  };

  const handleOpenFlowLogin = async () => {
    setIsOpeningFlowLogin(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await mediaStudioApi.openGoogleFlowLogin();
      setSuccessMessage("Đã gửi yêu cầu kết nối Google Flow. Vui lòng hoàn tất xác thực trên trình duyệt.");
    } catch (err: any) {
      setErrorMessage(err.message || "Không thể mở đăng nhập Google Flow.");
    } finally {
      setIsOpeningFlowLogin(false);
    }
  };

  
  const handleCompilePrompt = async () => {
    if (!videoPrompt.trim()) return;
    setIsCompiling(true);
    setErrorMessage(null);
    try {
      const res = await mediaStudioApi.compileVideoPrompt({
        prompt: videoPrompt,
        aspect_ratio: "16:9",
        duration_seconds: 10,
      });
      setCompiledPrompt(res);
    } catch (err: any) {
      setErrorMessage(err.message || "Không thể biên dịch câu lệnh");
    } finally {
      setIsCompiling(false);
    }
  };

  const handleCopyDirective = () => {
    if (!compiledPrompt) return;
    navigator.clipboard.writeText(compiledPrompt.compiled_directive);
    setCopiedDirective(true);
    setTimeout(() => setCopiedDirective(false), 2000);
  };

  const handleUploadReferenceImage = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setErrorMessage("Chỉ hỗ trợ tải ảnh làm khung hình tham chiếu.");
      e.target.value = "";
      return;
    }
    setIsUploadingReference(true);
    setErrorMessage(null);
    try {
      const asset = await mediaStudioApi.uploadAsset({ file, expected_category: "image" });
      setReferenceImage(asset);
      setSuccessMessage(`Đã thêm ảnh tham chiếu: ${asset.original_filename || asset.id}`);
    } catch (err: any) {
      setErrorMessage(err.message || "Không thể tải ảnh tham chiếu lên.");
    } finally {
      setIsUploadingReference(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleGenerateVideo = async () => {
    setIsGeneratingVideo(true);
    setErrorMessage(null);
    try {
      const res = await mediaStudioApi.generateVideo({
        prompt: videoPrompt,
        aspect_ratio: "9:16",
        use_official_omni: false,
        remove_watermark: false,
        start_image_asset_id: referenceImage?.id,
      });
      setGeneratedVideoPlaybackUrl(await mediaStudioApi.createAssetObjectUrl(res.url || ""));
      setGeneratedVideo(res);
    } catch (err: any) {
      setErrorMessage(err.message || "Không thể tạo video");
    } finally {
      setIsGeneratingVideo(false);
    }
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Top Banner with Credit Indicator */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Trung Tâm Sáng Tạo AI (AI Studio)
            </h1>
            <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
              Google Flow & Media Studio Active
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Dây chuyền tạo nhạc và video dọc 9:16 chất lượng cao tích hợp chuẩn TikTok.
          </p>
        </div>

        {/* Credit Indicator */}
        <div className="flex flex-wrap items-center justify-end gap-3">
          <Button
            size="sm"
            variant="outline"
            onClick={handleOpenFlowLogin}
            disabled={isOpeningFlowLogin}
            className="h-8 text-xs font-semibold rounded-lg gap-1.5"
          >
            {isOpeningFlowLogin ? <Loader2 className="size-3.5 animate-spin" /> : <ShieldCheck className="size-3.5" />}
            <span>{isOpeningFlowLogin ? "Đang kết nối..." : "Kết nối Google Flow"}</span>
          </Button>

          <Button
            size="sm"
            onClick={() => router.push("/video-studio")}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
          >
            <Video className="size-3.5" />
            <span>Mở Video Studio 9:16</span>
          </Button>
        </div>
      </div>

      {/* INTERACTIVE GENERATIVE MEDIA STUDIO CARD */}
      <Card className="rounded-2xl border-primary/30 bg-gradient-to-b from-card to-primary/5 shadow-sm overflow-hidden">
        <CardHeader className="p-5 pb-3 border-b border-border/50">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base font-bold text-foreground flex items-center gap-2">
                <Sparkles className="size-4 text-primary" />
                <span>Trạm Tạo Truyền Thông Trực Tiếp (Flow Engine)</span>
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground">
                Khởi tạo bài hát, phân cảnh video và hòa âm tự động chuẩn -14 LUFS hoàn toàn miễn phí.
              </CardDescription>
            </div>
            
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 text-xs">
                <ShieldCheck className="size-3 mr-1" />
                TikTok Safe Zone Ready
              </Badge>
              <Badge variant="outline" className="border-blue-500/40 text-blue-600 dark:text-blue-400 bg-blue-500/10 text-xs">
                -14 LUFS Normalized
              </Badge>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-5 space-y-4">
          {successMessage && (
            <div className="p-3 text-xs rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300">
              {successMessage}
            </div>
          )}
          {errorMessage && (
            <div className="p-3 text-xs rounded-xl bg-destructive/10 border border-destructive/20 text-destructive flex items-center gap-2">
              <AlertCircle className="size-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <Tabs value={activeMediaTab} onValueChange={(v) => setActiveMediaTab(v as any)} className="w-full">
            <TabsList className="grid w-full grid-cols-2 max-w-md h-9 p-1 bg-muted/60 rounded-xl">
              <TabsTrigger value="music" className="text-xs rounded-lg flex items-center gap-1.5">
                <Music className="size-3.5" />
                <span>Tạo Nhạc Flow Music</span>
              </TabsTrigger>
              <TabsTrigger value="video" className="text-xs rounded-lg flex items-center gap-1.5">
                <Video className="size-3.5" />
                <span>Tạo Video Dọc 9:16</span>
              </TabsTrigger>
            </TabsList>

            {/* TAB 1: MUSIC GENERATION */}
            <TabsContent value="music" className="space-y-4 pt-3">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-2 space-y-3">
                  <div>
                    <Label className="text-xs font-semibold text-foreground">Prompt Mô Tả Âm Nhạc</Label>
                    <Input
                      value={musicPrompt}
                      onChange={(e) => setMusicPrompt(e.target.value)}
                      placeholder="Mô tả phong cách, nhạc cụ, cảm xúc bài hát..."
                      className="mt-1 h-9 text-xs rounded-xl bg-background"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label className="text-xs font-semibold text-foreground">Thể Loại (Genre)</Label>
                      <select
                        value={musicGenre}
                        onChange={(e) => setMusicGenre(e.target.value)}
                        className="mt-1 w-full h-9 px-3 rounded-xl border border-input bg-background text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                      >
                        <option value="Acoustic">Acoustic Guitar</option>
                        <option value="Lo-Fi">Lo-Fi Chill Hop</option>
                        <option value="Pop">Upbeat Pop</option>
                        <option value="EDM">EDM Energetic</option>
                        <option value="Cinematic">Cinematic Dramatic</option>
                      </select>
                    </div>
                    <div>
                      <Label className="text-xs font-semibold text-foreground">Tâm Trạng (Mood)</Label>
                      <select
                        value={musicMood}
                        onChange={(e) => setMusicMood(e.target.value)}
                        className="mt-1 w-full h-9 px-3 rounded-xl border border-input bg-background text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                      >
                        <option value="Relaxing">Thư Thái (Relaxing)</option>
                        <option value="Upbeat">Sôi Nổi (Upbeat)</option>
                        <option value="Inspirational">Truyền Cảm Hứng</option>
                        <option value="Dramatic">Kịch Tính</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label className="text-xs font-semibold text-foreground">Nhà Cung Cấp (Provider)</Label>
                      <select
                        value={musicProvider}
                        onChange={(e) => setMusicProvider(e.target.value as any)}
                        className="mt-1 w-full h-9 px-3 rounded-xl border border-input bg-background text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                      >
                        <option value="FLOW_BROWSER_PILOT">Google Flow Music (Mặc định)</option>
                        <option value="GOOGLE_OFFICIAL">Google Lyria Official</option>
                      </select>
                    </div>
                    <div>
                      <Label className="text-xs font-semibold text-foreground">Định Dạng Sinh</Label>
                      <Input
                        value={musicProvider === "GOOGLE_OFFICIAL" ? "Lyria Clip Preview (30s)" : "Flow Track (Chuẩn TikTok)"}
                        disabled
                        className="mt-1 h-9 text-xs bg-muted/50 rounded-xl"
                      />
                    </div>
                  </div>

                  <Button
                    onClick={handleGenerateMusic}
                    disabled={isGeneratingMusic}
                    className="w-full h-9 text-xs font-semibold rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground gap-2"
                  >
                    {isGeneratingMusic ? (
                      <>
                        <Loader2 className="size-3.5 animate-spin" />
                        <span>
                          {musicProvider === "GOOGLE_OFFICIAL"
                            ? "Đang gọi Google Lyria Interactions API..."
                            : "Đang render âm thanh qua Flow Music Plus..."}
                        </span>
                      </>
                    ) : (
                      <>
                        <Music className="size-3.5" />
                        <span>
                          {musicProvider === "GOOGLE_OFFICIAL"
                            ? "Khởi Tạo Nhạc Lyria"
                            : "Khởi Tạo Bài Hát (Flow Music)"}
                        </span>
                      </>
                    )}
                  </Button>
                </div>

                {/* Output Preview */}
                <div className="p-4 rounded-xl border border-border/80 bg-background/80 flex flex-col justify-between space-y-3">
                  <div className="space-y-2">
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
                      Kết Quả Render Âm Thanh
                    </span>
                    {generatedMusic ? (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="size-4 text-emerald-500" />
                          <span className="text-xs font-bold text-foreground truncate">{generatedMusic.original_filename}</span>
                        </div>
                        <div className="flex items-center gap-2 pt-1">
                          <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-600 border-emerald-500/30">
                            Chuẩn âm thanh TikTok (-14 LUFS)
                          </Badge>
                        </div>
                        <audio controls className="w-full h-8 mt-2" src={generatedMusicPlaybackUrl || undefined} />
                      </div>
                    ) : (
                      <div className="text-center py-6 text-muted-foreground text-xs">
                        <Music className="size-8 mx-auto mb-2 opacity-30" />
                        Chưa có bản ghi nào. Nhấn nút tạo để nghe thử.
                      </div>
                    )}
                  </div>

                  {generatedMusic && (
                    <Button variant="outline" size="sm" className="w-full h-8 text-xs gap-1.5 rounded-lg" onClick={() => handleDownloadAsset(generatedMusic)} disabled={!generatedMusic.url}>
                      <Download className="size-3" />
                      <span>Tải Tệp MP3 Chuẩn Hóa</span>
                    </Button>
                  )}
                </div>
              </div>
            </TabsContent>

            {/* TAB 2: VIDEO GENERATION */}
            <TabsContent value="video" className="space-y-4 pt-3">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleUploadReferenceImage}
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
              />

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-2 space-y-3">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <Label className="text-xs font-semibold text-foreground">Yêu Cầu / Ý Tưởng Video B-Roll</Label>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={handleCompilePrompt}
                        disabled={isCompiling || !videoPrompt.trim()}
                        className="h-6 px-2 text-[11px] font-semibold text-primary hover:text-primary hover:bg-primary/10 gap-1 rounded-lg"
                      >
                        {isCompiling ? (
                          <>
                            <Loader2 className="size-3 animate-spin" />
                            <span>Đang phân tích...</span>
                          </>
                        ) : (
                          <>
                            <Wand2 className="size-3" />
                            <span>Tối Ưu Bộ Lệnh & Xem Hướng Dẫn</span>
                          </>
                        )}
                      </Button>
                    </div>
                    <Input
                      value={videoPrompt}
                      onChange={(e) => setVideoPrompt(e.target.value)}
                      placeholder="Ví dụ: Cảnh quay cận cảnh ly cà phê sữa đá nhỏ giọt dưới ánh nắng ban mai..."
                      className="h-9 text-xs rounded-xl bg-background"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs font-semibold text-foreground">Ảnh tham chiếu (không bắt buộc)</Label>
                    {referenceImage ? (
                      <div className="flex items-center gap-3 rounded-xl border border-border bg-background p-2">
                        {referenceImage.url && (
                          <img src={referenceImage.url} alt="Ảnh tham chiếu đã chọn" className="size-14 rounded-lg object-cover" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs font-medium">{referenceImage.original_filename || referenceImage.id}</p>
                          <p className="text-[10px] text-muted-foreground">Flow sẽ dùng ảnh này làm khung hình đầu.</p>
                        </div>
                        <Button type="button" variant="ghost" size="sm" onClick={() => setReferenceImage(null)} className="h-7 px-2 text-xs">
                          Bỏ ảnh
                        </Button>
                      </div>
                    ) : (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={isUploadingReference || isGeneratingVideo}
                        className="h-9 w-full justify-start gap-2 rounded-xl border-dashed text-xs"
                      >
                        {isUploadingReference ? <Loader2 className="size-3.5 animate-spin" /> : <Upload className="size-3.5" />}
                        <span>{isUploadingReference ? "Đang tải ảnh..." : "Tải ảnh tham chiếu lên"}</span>
                      </Button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label className="text-xs font-semibold text-foreground">Tỷ Lệ Khung Hình Đích</Label>
                      <Input value="Dọc 9:16 (1080 x 1920 px) Chuẩn TikTok" disabled className="mt-1 h-9 text-xs bg-muted/50 rounded-xl" />
                    </div>
                    <div>
                      <Label className="text-xs font-semibold text-foreground">Nguồn Sinh Video</Label>
                      <select className="mt-1 w-full h-9 px-3 rounded-xl border border-input bg-background text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary">
                        <option value="flow">Google Flow Pro (Omni Flash 10s)</option>
                        <option value="omni">Google Flow (Official Pro Account)</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-2 pt-1">
                    <Button
                      onClick={handleGenerateVideo}
                      disabled={isGeneratingVideo || isUploadingReference}
                      className="h-9 text-xs font-semibold rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground gap-2"
                    >
                      {isGeneratingVideo ? (
                        <>
                          <Loader2 className="size-3.5 animate-spin" />
                          <span>{referenceImage ? "Đang tạo video từ ảnh..." : "Đang điều phối Google Flow..."}</span>
                        </>
                      ) : (
                        <>
                          <Video className="size-3.5" />
                          <span>Tạo Video Dọc 9:16</span>
                        </>
                      )}
                    </Button>

                  </div>
                </div>

                {/* Video Output Preview */}
                <div className="p-4 rounded-xl border border-border/80 bg-background/80 flex flex-col justify-between space-y-3">
                  <div className="space-y-2">
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
                      Xem Trước Video Dọc (9:16)
                    </span>
                    {generatedVideo ? (
                      <div className="space-y-2">
                        <div className="relative aspect-[9/16] max-h-56 mx-auto rounded-lg overflow-hidden border border-border bg-black shadow-md">
                          <video src={generatedVideoPlaybackUrl || undefined} controls className="w-full h-full object-cover" />
                          <div className="absolute top-2 left-2 px-1.5 py-0.5 rounded text-[9px] font-bold bg-primary/80 text-white">
                            9:16 TikTok
                          </div>
                        </div>
                        <div className="text-[10px] text-muted-foreground font-mono text-center truncate">
                          {generatedVideo.original_filename}
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-8 text-muted-foreground text-xs">
                        <Video className="size-8 mx-auto mb-2 opacity-30" />
                        Chưa có video. Nhập mô tả, thêm ảnh tham chiếu nếu cần, rồi tạo video.
                      </div>
                    )}
                  </div>

                  {generatedVideo && (
                    <Button variant="outline" size="sm" className="w-full h-8 text-xs gap-1.5 rounded-lg" onClick={() => handleDownloadAsset(generatedVideo)} disabled={!generatedVideo.url}>
                      <Download className="size-3" />
                      <span>Tải Tệp Video MP4 (1080x1920)</span>
                    </Button>
                  )}
                </div>
              </div>

              {/* BỘ LỆNH & HƯỚNG DẪN CHI TIẾT TỪ YÊU CẦU NGƯỜI DÙNG */}
              {compiledPrompt && (
                <div className="mt-4 p-4 rounded-2xl border border-primary/20 bg-primary/5 space-y-3 text-xs">
                  <div className="flex items-center justify-between border-b border-primary/10 pb-2">
                    <div className="flex items-center gap-2">
                      <BookOpen className="size-4 text-primary" />
                      <span className="font-bold text-foreground">Bộ Lệnh & Hướng Dẫn Phân Cảnh Chi Tiết Cho Creator</span>
                    </div>
                    <Badge variant="outline" className="bg-primary/10 text-primary border-primary/30 text-[10px]">
                      {compiledPrompt.model_target} - {compiledPrompt.target_duration_seconds}s
                    </Badge>
                  </div>

                  {/* Compiled Prompt Box with Copy */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                      <span className="font-semibold text-foreground">Bộ Lệnh Chuẩn Google Flow (Copy & Paste nếu cần):</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={handleCopyDirective}
                        className="h-6 px-2 text-[10px] gap-1 text-primary hover:bg-primary/10"
                      >
                        {copiedDirective ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                        <span>{copiedDirective ? "Đã chép lệnh" : "Sao chép lệnh"}</span>
                      </Button>
                    </div>
                    <div className="p-2.5 rounded-xl bg-background border border-border font-mono text-[11px] leading-relaxed text-foreground select-all">
                      {compiledPrompt.compiled_directive}
                    </div>
                  </div>

                  {/* 4 Phân tích chuyên sâu */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 pt-1">
                    <div className="p-2.5 rounded-xl bg-background/80 border border-border/60 space-y-1">
                      <span className="text-[10px] font-semibold text-muted-foreground uppercase block">Góc Máy & Chuyển Động</span>
                      <div className="text-[11px] text-foreground font-medium">{compiledPrompt.shot_type}</div>
                      <div className="text-[10px] text-muted-foreground">{compiledPrompt.camera_movement}</div>
                    </div>
                    <div className="p-2.5 rounded-xl bg-background/80 border border-border/60 space-y-1">
                      <span className="text-[10px] font-semibold text-muted-foreground uppercase block">Ánh Sáng & Không Khí</span>
                      <div className="text-[11px] text-foreground font-medium">{compiledPrompt.lighting_atmosphere}</div>
                    </div>
                    <div className="p-2.5 rounded-xl bg-background/80 border border-border/60 space-y-1">
                      <span className="text-[10px] font-semibold text-muted-foreground uppercase block">Động Học Vật Lý</span>
                      <div className="text-[11px] text-foreground font-medium">{compiledPrompt.kinetic_action}</div>
                    </div>
                    <div className="p-2.5 rounded-xl bg-background/80 border border-border/60 space-y-1">
                      <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase block">Điểm Móc 3 Giây Đầu</span>
                      <div className="text-[11px] text-foreground font-medium">{compiledPrompt.retention_hook_3s}</div>
                    </div>
                  </div>

                  {/* Cues Âm Thanh & Hướng dẫn */}
                  <div className="pt-1 border-t border-primary/10 flex flex-col md:flex-row md:items-center justify-between gap-2 text-[11px] text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                      <Music className="size-3.5 text-primary shrink-0" />
                      <span><strong>Âm thanh gợi ý:</strong> {compiledPrompt.suggested_audio_sfx}</span>
                    </div>
                    <div className="text-[10px] text-primary font-medium">
                      Tự động kích hoạt khi nhấn 'Khởi Tạo Video Dọc 9:16'
                    </div>
                  </div>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Category Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {["all", "writing", "audio", "visual", "video", "seo"].map((cat) => (
          <Button
            key={cat}
            variant={selectedCategory === cat ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedCategory(cat)}
            className="h-8 text-xs rounded-xl capitalize"
          >
            {cat === "all" ? "Tất Cả Công Cụ" : cat}
          </Button>
        ))}
      </div>

      {/* Tool Cards Grid (Visual & Premium) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {filteredTools.map((tool) => {
          const Icon = tool.icon;

          return (
            <Card
              key={tool.id}
              onClick={() => router.push(tool.route)}
              className="group rounded-2xl border-border/80 bg-card hover:border-primary/50 transition-all cursor-pointer p-4 flex flex-col justify-between space-y-4 shadow-xs hover:shadow-md"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="size-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center group-hover:scale-105 transition-transform">
                    <Icon className="size-5" />
                  </div>
                  <Badge variant="outline" className="text-[10px] font-semibold border-primary/30 text-primary bg-primary/5">
                    {tool.badge}
                  </Badge>
                </div>

                <div className="space-y-1">
                  <h3 className="text-sm font-bold text-foreground group-hover:text-primary transition-colors">
                    {tool.name}
                  </h3>
                  <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                    {tool.description}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-border/50 text-xs">
                <span className="text-[11px] font-mono text-muted-foreground flex items-center gap-1">
                  <Coins className="size-3 text-primary" /> {tool.credits} BAHA Group / lần
                </span>
                <span className="text-primary font-semibold flex items-center gap-1 group-hover:translate-x-0.5 transition-transform text-[11px]">
                  Mở công cụ <ArrowRight className="size-3" />
                </span>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Active AI Generation Jobs Tracker */}
      <div className="space-y-3 pt-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-foreground">Hàng Đợi Xử Lý Nền (Background Jobs)</h2>
            <Badge variant="secondary" className="text-[10px] font-mono">
              {jobs.filter((j) => j.status === "processing").length} Đang chạy
            </Badge>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setJobs([...jobs])}
            className="h-7 text-xs text-muted-foreground hover:text-foreground gap-1"
          >
            <RotateCw className="size-3" />
            <span>Làm mới trạng thái</span>
          </Button>
        </div>

        <div className="space-y-2">
          {jobs.map((job) => {
            const isProcessing = job.status === "processing";
            const isCompleted = job.status === "completed";
            const isFailed = job.status === "failed";

            return (
              <div
                key={job.id}
                className="flex flex-col md:flex-row md:items-center justify-between p-3.5 rounded-xl border border-border/70 bg-card gap-3 text-xs"
              >
                <div className="flex items-center gap-3">
                  <div className="size-8 rounded-lg bg-muted flex items-center justify-center shrink-0">
                    {isProcessing && <RotateCw className="size-4 text-primary animate-spin" />}
                    {isCompleted && <CheckCircle2 className="size-4 text-emerald-500" />}
                    {isFailed && <AlertCircle className="size-4 text-destructive" />}
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-foreground">{job.title}</span>
                      <span className="text-[10px] font-mono text-muted-foreground">ID: {job.id}</span>
                    </div>
                    <p className="text-[11px] text-muted-foreground">{(job.meta?.prompt || job.type)}</p>
                  </div>
                </div>

                <div className="flex items-center gap-4 justify-between md:justify-end">
                  {isProcessing && (
                    <div className="w-32 space-y-1">
                      <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
                        <span>Đang xử lý</span>
                        <span>{job.progress}%</span>
                      </div>
                      <Progress value={job.progress} className="h-1.5" />
                    </div>
                  )}

                  {isCompleted && (
                    <Badge variant="outline" className="border-emerald-500/30 text-emerald-600 bg-emerald-500/5 text-[10px]">
                      Hoàn thành
                    </Badge>
                  )}

                  {isFailed && (
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="border-destructive/30 text-destructive bg-destructive/5 text-[10px]">
                        Thất bại
                      </Badge>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleRetry(job.id)}
                        className="h-6 px-2 text-[10px] text-primary hover:bg-primary/10"
                      >
                        Thử lại
                      </Button>
                    </div>
                  )}

                  <span className="text-[10px] font-mono text-muted-foreground flex items-center gap-1">
                    <Clock className="size-3" /> {job.createdAt}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

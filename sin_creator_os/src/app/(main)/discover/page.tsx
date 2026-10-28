"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Filter,
  Sparkles,
  TrendingUp,
  SlidersHorizontal,
  Flame,
  ShieldCheck,
  RotateCw,
  ExternalLink,
  ChevronDown,
  Layers,
  Zap,
  Loader2,
  Database,
} from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ContentCard } from "@/components/creator/content-card";
import { DiscoverService } from "@/services/discover-service";
import { ContentItem } from "@/types";

export default function DiscoverPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = React.useState("");
  const [selectedNiche, setSelectedNiche] = React.useState("all");
  const [selectedPeriod, setSelectedPeriod] = React.useState("7d");
  const [selectedSort, setSelectedSort] = React.useState("trending");
  const [showAdvancedFilters, setShowAdvancedFilters] = React.useState(false);
  const [minViews, setMinViews] = React.useState("100k");
  const [videos, setVideos] = React.useState<ContentItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [isRefreshing, setIsRefreshing] = React.useState(false);

  const loadVideos = React.useCallback(async () => {
    try {
      const data = await DiscoverService.searchContent({
        query: searchQuery,
        niche: selectedNiche,
      });
      setVideos(data);
    } catch {
      // Error
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [searchQuery, selectedNiche]);

  React.useEffect(() => {
    loadVideos();
  }, [loadVideos]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadVideos();
  };

  // Filter content client-side
  const filteredVideos = React.useMemo(() => {
    let list = [...videos];
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (v) =>
          v.title.toLowerCase().includes(q) ||
          v.caption.toLowerCase().includes(q) ||
          v.detectedTopic.toLowerCase().includes(q) ||
          v.channelName.toLowerCase().includes(q)
      );
    }
    if (selectedNiche !== "all") {
      list = list.filter((v) =>
        v.contentPillar.toLowerCase().includes(selectedNiche.toLowerCase())
      );
    }
    return list;
  }, [videos, searchQuery, selectedNiche]);

  return (
    <div className="space-y-6 pb-12">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Khám Phá Nội Dung &amp; Xu Hướng (Discover)
            </h1>
            <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20 text-xs">
              Evidence-Backed Inspiration
            </Badge>
            <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 bg-emerald-500/10 text-xs font-semibold gap-1">
              <Database className="size-3" /> Đã đồng bộ ({videos.length} Nguồn)
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Tìm kiếm video TikTok thực tế đang tăng trưởng đột biến kèm số liệu và cấu trúc để chuyển hóa thành ý tưởng mới.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="h-8 text-xs font-medium rounded-lg gap-1.5"
          >
            <RotateCw className={`size-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
            <span>Làm mới</span>
          </Button>
          <Button
            size="sm"
            onClick={() => router.push("/ideas/generate")}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
          >
            <Sparkles className="size-3.5" />
            <span>Sinh Ý Tưởng Từ Trend Này</span>
          </Button>
        </div>
      </div>

      {/* Search Header & Primary Filters */}
      <div className="rounded-2xl border border-border/80 bg-card p-4 space-y-3.5 shadow-xs">
        <div className="flex flex-col md:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Tìm kiếm chủ đề, ngách (AI, affiliate, giáo dục...), creator hoặc từ khóa..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-10 text-xs rounded-xl bg-background border-border/80 focus-visible:ring-primary/30"
            />
          </div>

          <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
            {/* Niche selector */}
            <Select value={selectedNiche} onValueChange={setSelectedNiche}>
              <SelectTrigger className="h-10 text-xs rounded-xl min-w-[140px] bg-background">
                <SelectValue placeholder="Ngách nội dung" />
              </SelectTrigger>
              <SelectContent className="rounded-xl">
                <SelectItem value="all">Mọi ngách nội dung</SelectItem>
                <SelectItem value="Quy Trình & AI">Quy Trình &amp; AI</SelectItem>
                <SelectItem value="Chiến Lược Video Triệu View">Chiến Lược Video Triệu View</SelectItem>
              </SelectContent>
            </Select>

            {/* Time period */}
            <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
              <SelectTrigger className="h-10 text-xs rounded-xl min-w-[110px] bg-background">
                <SelectValue placeholder="Thời gian" />
              </SelectTrigger>
              <SelectContent className="rounded-xl">
                <SelectItem value="today">24 giờ qua</SelectItem>
                <SelectItem value="7d">7 ngày qua</SelectItem>
                <SelectItem value="30d">30 ngày qua</SelectItem>
                <SelectItem value="all">Toàn bộ</SelectItem>
              </SelectContent>
            </Select>

            {/* Sort by */}
            <Select value={selectedSort} onValueChange={setSelectedSort}>
              <SelectTrigger className="h-10 text-xs rounded-xl min-w-[130px] bg-background">
                <SelectValue placeholder="Sắp xếp" />
              </SelectTrigger>
              <SelectContent className="rounded-xl">
                <SelectItem value="trending">Tăng trưởng nhanh (Velocity)</SelectItem>
                <SelectItem value="views">Nhiều lượt xem nhất</SelectItem>
                <SelectItem value="engagement">Tương tác cao nhất</SelectItem>
              </SelectContent>
            </Select>

            {/* Toggle Advanced Filters */}
            <Button
              variant={showAdvancedFilters ? "secondary" : "outline"}
              size="icon"
              onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
              className="h-10 w-10 shrink-0 rounded-xl"
              title="Bộ lọc nâng cao"
            >
              <SlidersHorizontal className="size-4" />
            </Button>
          </div>
        </div>

        {/* Expandable Advanced Filters */}
        {showAdvancedFilters && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 pt-3 border-t border-border/60 text-xs animate-in fade-in slide-in-from-top-2">
            <div>
              <label className="text-muted-foreground block mb-1 text-[11px] font-medium">Quốc gia</label>
              <Select defaultValue="vn">
                <SelectTrigger className="h-8 rounded-lg text-xs bg-background">
                  <SelectValue placeholder="Quốc gia" />
                </SelectTrigger>
                <SelectContent className="rounded-xl">
                  <SelectItem value="vn">Việt Nam</SelectItem>
                  <SelectItem value="us">Hoa Kỳ</SelectItem>
                  <SelectItem value="global">Toàn cầu</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-muted-foreground block mb-1 text-[11px] font-medium">Lượt xem tối thiểu</label>
              <Select value={minViews} onValueChange={setMinViews}>
                <SelectTrigger className="h-8 rounded-lg text-xs bg-background">
                  <SelectValue placeholder="Min Views" />
                </SelectTrigger>
                <SelectContent className="rounded-xl">
                  <SelectItem value="50k">&gt; 50.000</SelectItem>
                  <SelectItem value="100k">&gt; 100.000</SelectItem>
                  <SelectItem value="500k">&gt; 500.000</SelectItem>
                  <SelectItem value="1m">&gt; 1.000.000</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-muted-foreground block mb-1 text-[11px] font-medium">Thời lượng video</label>
              <Select defaultValue="all">
                <SelectTrigger className="h-8 rounded-lg text-xs bg-background">
                  <SelectValue placeholder="Thời lượng" />
                </SelectTrigger>
                <SelectContent className="rounded-xl">
                  <SelectItem value="all">Mọi thời lượng</SelectItem>
                  <SelectItem value="under30">&lt; 30 giây (Optimal)</SelectItem>
                  <SelectItem value="30to60">30 - 60 giây</SelectItem>
                  <SelectItem value="over60">&gt; 60 giây</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-muted-foreground block mb-1 text-[11px] font-medium">Tỉ lệ tương tác (ER)</label>
              <Select defaultValue="5">
                <SelectTrigger className="h-8 rounded-lg text-xs bg-background">
                  <SelectValue placeholder="Tỉ lệ ER" />
                </SelectTrigger>
                <SelectContent className="rounded-xl">
                  <SelectItem value="all">Mọi mức</SelectItem>
                  <SelectItem value="5">&gt; 5% Tương tác</SelectItem>
                  <SelectItem value="8">&gt; 8% Rất cao</SelectItem>
                  <SelectItem value="10">&gt; 10% Đột biến</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-muted-foreground block mb-1 text-[11px] font-medium">Nguồn dữ liệu</label>
              <Select defaultValue="tiktok">
                <SelectTrigger className="h-8 rounded-lg text-xs bg-background">
                  <SelectValue placeholder="Nguồn" />
                </SelectTrigger>
                <SelectContent className="rounded-xl">
                  <SelectItem value="tiktok">TikTok Organic Feed</SelectItem>
                  <SelectItem value="competitors">Kênh đối thủ</SelectItem>
                  <SelectItem value="audio">Trending Sounds</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )}
      </div>

      {/* Evidence Principle Notice Callout */}
      <div className="flex items-center justify-between p-3.5 rounded-xl bg-primary/5 border border-primary/20 text-xs">
        <div className="flex items-center gap-2.5">
          <div className="size-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <ShieldCheck className="size-4" />
          </div>
          <div>
            <span className="font-semibold text-foreground">Nguyên Tắc Bằng Chứng Thực Tế (Evidence Principle):</span>
            <p className="text-[11px] text-muted-foreground">
              Mọi tư liệu nguồn BAHA Group gợi ý đều có nguồn tham chiếu rõ ràng (video URL, thời điểm thu thập, số liệu thật và lý do thành công), tuyệt đối không suy đoán vô căn cứ.
            </p>
          </div>
        </div>

        <Badge variant="outline" className="hidden sm:inline-flex border-primary/30 text-primary text-[10px]">
          100% Provenance
        </Badge>
      </div>

      {/* Content Discovery Cards Grid */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-24 text-muted-foreground space-y-3">
          <Loader2 className="size-8 animate-spin text-primary" />
          <p className="text-xs">Đang tải danh sách video nguồn...</p>
        </div>
      ) : filteredVideos.length === 0 ? (
        <div className="text-center py-20 border rounded-2xl bg-card space-y-3">
          <Layers className="size-10 mx-auto text-muted-foreground/60" />
          <h3 className="font-semibold text-sm">Không có dữ liệu video nguồn</h3>
          <p className="text-xs text-muted-foreground max-w-sm mx-auto">
            Không có dữ liệu video nào được ghi nhận hoặc phù hợp với bộ lọc hiện tại.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredVideos.map((content) => (
            <ContentCard
              key={content.id}
              content={content}
              onSave={(id) => console.log("Saved content:", id)}
              onGenerateIdea={(c) => router.push(`/ideas/generate?source=${c.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

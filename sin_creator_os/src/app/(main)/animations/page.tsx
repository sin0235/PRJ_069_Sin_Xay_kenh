"use client";

import * as React from "react";
import {
  Sparkles,
  Play,
  RotateCcw,
  Zap,
  TrendingUp,
  Flame,
  Music2,
  Film,
  CheckCircle2,
  Eye,
  Heart,
  Share2,
  Layers,
  Activity,
  Cpu,
} from "lucide-react";
import {
  SpotlightCard,
  BorderBeam,
  TiltCard,
  NumberTicker,
  InfiniteMarquee,
  ShimmerButton,
  triggerGlobalVectorConfetti,
  ParticleConstellationCanvas,
} from "@/components/creator/motion-primitives";
import {
  StatusBeacon,
  SoundEqualizer,
  ShimmerProgressBar,
  FloatingSparkleSVG,
} from "@/components/creator/dynamic-visuals";

const TRENDING_AUDIOS = [
  { title: "Flow Beat TikTok Viral", author: "Baha Music AI", duration: "0:45", plays: "450K" },
  { title: "Năng Lượng Sáng Tạo Sin", author: "Sin Creator", duration: "1:00", plays: "320K" },
  { title: "Ambient Cinematic Lo-Fi", author: "DJ Sin Sound", duration: "0:30", plays: "180K" },
  { title: "Bass Drop Tech Review", author: "Tech Lab VN", duration: "0:15", plays: "610K" },
];

const TRENDING_TAGS = [
  "#SinCreatorOS",
  "#XayKenhTikTokAI",
  "#VideoStudioBaha",
  "#TuDongDungVideo",
  "#TikTokVietnam2026",
  "#KaraokeVietsubV2",
  "#AIContentCreator",
];

export default function AnimationsShowcasePage() {
  const [tickerKey, setTickerKey] = React.useState<number>(0);
  const [isPlayingAudio, setIsPlayingAudio] = React.useState<boolean>(true);
  const [progressVal, setProgressVal] = React.useState<number>(68);

  const handleConfetti = (e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    triggerGlobalVectorConfetti({
      x: rect.left + rect.width / 2,
      y: rect.top,
    });
  };

  const handleRestartTickers = () => {
    setTickerKey((prev) => prev + 1);
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-16">
      {/* 1. Header & Hero Action */}
      <div className="relative rounded-2xl border border-border bg-gradient-to-br from-card via-card to-primary/5 p-6 md:p-8 overflow-hidden shadow-xs">
        <BorderBeam size={280} duration={8} colorFrom="#2b6fb8" colorTo="#60a5fa" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/25 bg-primary/10 text-primary text-xs font-medium">
              <FloatingSparkleSVG size={14} className="text-primary" />
              <span>Hạ Tầng Hiệu Ứng Chuyển Động (BAHA Dynamic Motion System)</span>
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-foreground">
              Phòng Trưng Bày & Thử Nghiệm Hiệu Ứng Động
            </h1>
            <p className="text-muted-foreground text-sm md:text-base leading-relaxed">
              Tập hợp các giải pháp animation tăng tốc phần cứng GPU, tương tác vật lý vi mô 3D,
              băng chuyền vô tận và pháo hoa vector SVG thuần túy tuân thủ nghiêm ngặt chuẩn mực BAHA V2.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <ShimmerButton onClick={handleConfetti} variant="primary" className="py-2.5 px-5 shadow-lg">
              <Sparkles className="size-4" />
              <span>Bắn pháo hoa ăn mừng</span>
            </ShimmerButton>
            <button
              onClick={handleRestartTickers}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-border bg-background hover:bg-muted text-sm font-medium transition-colors cursor-pointer"
            >
              <RotateCcw className="size-4" />
              <span>Chạy lại số liệu</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. Thống Kê Lăn Số (NumberTicker) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="size-5 text-primary" />
            <h2 className="text-lg font-bold text-foreground">Bộ Đếm Số Lăn Mượt (NumberTicker)</h2>
          </div>
          <span className="text-xs text-muted-foreground font-mono">Thuật toán Exponential Easing (easeOutExpo)</span>
        </div>

        <div key={tickerKey} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <SpotlightCard className="p-5">
            <div className="flex items-center justify-between text-muted-foreground mb-3">
              <span className="text-xs font-medium uppercase tracking-wider">Tổng Lượt Xem Kênh</span>
              <Eye className="size-4 text-primary" />
            </div>
            <div className="text-3xl font-bold text-foreground">
              <NumberTicker value={1458920} duration={1.8} />
            </div>
            <p className="text-xs text-emerald-600 font-medium mt-2 flex items-center gap-1">
              <span>+18.4%</span> so với tuần trước
            </p>
          </SpotlightCard>

          <SpotlightCard className="p-5">
            <div className="flex items-center justify-between text-muted-foreground mb-3">
              <span className="text-xs font-medium uppercase tracking-wider">Lượt Tương Tác Video</span>
              <Heart className="size-4 text-rose-500" />
            </div>
            <div className="text-3xl font-bold text-foreground">
              <NumberTicker value={128450} duration={1.6} />
            </div>
            <p className="text-xs text-emerald-600 font-medium mt-2 flex items-center gap-1">
              <span>+9.2%</span> tỉ lệ thả tim
            </p>
          </SpotlightCard>

          <SpotlightCard className="p-5">
            <div className="flex items-center justify-between text-muted-foreground mb-3">
              <span className="text-xs font-medium uppercase tracking-wider">Kịch Bản Đã Xuất Bản</span>
              <Film className="size-4 text-amber-500" />
            </div>
            <div className="text-3xl font-bold text-foreground">
              <NumberTicker value={74} duration={1.4} suffix=" kịch bản" />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              100% đạt chuẩn Safe Zone TikTok
            </p>
          </SpotlightCard>

          <SpotlightCard className="p-5">
            <div className="flex items-center justify-between text-muted-foreground mb-3">
              <span className="text-xs font-medium uppercase tracking-wider">Thời Lượng Video Render</span>
              <Activity className="size-4 text-sky-500" />
            </div>
            <div className="text-3xl font-bold text-foreground">
              <NumberTicker value={38.5} decimalPlaces={1} duration={1.7} suffix=" giờ" />
            </div>
            <p className="text-xs text-emerald-600 font-medium mt-2">
              Tăng tốc GPU phần cứng chuẩn
            </p>
          </SpotlightCard>
        </div>
      </section>

      {/* 3. Tương Tác Vật Lý 3D & Hào Quang (TiltCard & BorderBeam) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="size-5 text-primary" />
            <h2 className="text-lg font-bold text-foreground">Thẻ Vật Lý 3D & Tia Sáng Laser (TiltCard & BorderBeam)</h2>
          </div>
          <span className="text-xs text-muted-foreground">Rê chuột để trải nghiệm góc nghiêng và ánh sáng phản quang Glare</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: 3D Tilt Card mô phỏng Video Dọc TikTok */}
          <TiltCard className="p-6 flex flex-col justify-between h-80 bg-gradient-to-b from-card to-muted/40 cursor-pointer">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20">
                  Dọc 9:16 (1080×1920)
                </span>
                <StatusBeacon status="processing" size="sm" showIcon />
              </div>
              <h3 className="text-base font-semibold text-foreground leading-snug">
                Review Công Nghệ Sin: Bí Quyết Đạt Triệu View Tự Nhiên
              </h3>
              <p className="text-xs text-muted-foreground line-clamp-3">
                Kịch bản dựng tự động qua Auto Edit, kết hợp giọng đọc AI Sin ấm áp, phụ đề karaoke vietsub và hiệu ứng phóng to cutaway.
              </p>
            </div>

            <div className="pt-4 border-t border-border/80 flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-mono">36.7 giây • 30 fps</span>
              <span className="text-primary font-medium flex items-center gap-1">
                <Play className="size-3 fill-current" /> Xem thử 3D
              </span>
            </div>
          </TiltCard>

          {/* Card 2: Thẻ BorderBeam nổi bật đặc biệt */}
          <div className="relative rounded-xl border border-primary/30 bg-card p-6 flex flex-col justify-between h-80 overflow-hidden shadow-md">
            <BorderBeam size={220} duration={6} colorFrom="#2b6fb8" colorTo="#38bdf8" />
            <div className="space-y-3 relative z-10">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                  Tác Vụ Ưu Tiên VIP
                </span>
                <span className="text-xs font-mono text-muted-foreground">ID: #JOB-069-AI</span>
              </div>
              <h3 className="text-base font-bold text-foreground">
                Bộ Dựng Auto Edit Video Thông Minh
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Đường truyền ánh sáng Laser (BorderBeam) tự động kích hoạt khi có tác vụ dựng nền đang hoạt động, giúp người dùng nhận biết tức thì.
              </p>
              <div className="space-y-1.5 pt-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Tiến trình kết xuất</span>
                  <span className="font-mono font-medium text-primary">{progressVal}%</span>
                </div>
                <ShimmerProgressBar value={progressVal} isProcessing={true} heightClass="h-2" />
              </div>
            </div>

            <div className="pt-4 border-t border-border flex items-center justify-between text-xs relative z-10">
              <span className="text-muted-foreground font-mono">Worker: NAS Synology</span>
              <span className="text-emerald-600 font-medium">Đang xử lý GPU</span>
            </div>
          </div>

          {/* Card 3: Thẻ Âm Thanh & Sóng Equalizer */}
          <TiltCard className="p-6 flex flex-col justify-between h-80 bg-gradient-to-b from-card to-primary/5">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-600 border border-amber-500/20">
                  Âm Nhạc Flow Beat
                </span>
                <SoundEqualizer isPlaying={isPlayingAudio} height={18} colorClass="bg-primary" />
              </div>
              <h3 className="text-base font-semibold text-foreground">
                Tạo Nhạc Nền AI Theo Cảm Xúc Kịch Bản
              </h3>
              <p className="text-xs text-muted-foreground">
                Tự động đồng bộ SFX tiếng click, lật trang, dồn lực theo chuẩn độ vang -14 LUFS cho nền tảng video ngắn TikTok.
              </p>
            </div>

            <div className="pt-4 border-t border-border flex items-center justify-between">
              <button
                onClick={() => setIsPlayingAudio(!isPlayingAudio)}
                className="text-xs text-primary font-medium flex items-center gap-1.5 hover:underline cursor-pointer"
              >
                <Music2 className="size-3.5" />
                <span>{isPlayingAudio ? "Tạm dừng phát" : "Bật nghe nhạc"}</span>
              </button>
              <span className="text-xs text-muted-foreground font-mono">-14 LUFS</span>
            </div>
          </TiltCard>
        </div>
      </section>

      {/* 4. Dải Băng Chuyền Vô Tận (InfiniteMarquee) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Flame className="size-5 text-amber-500" />
            <h2 className="text-lg font-bold text-foreground">Dải Băng Chuyền Vô Tận (InfiniteMarquee)</h2>
          </div>
          <span className="text-xs text-muted-foreground">Tự động tạm dừng khi rê chuột lên dải tin</span>
        </div>

        {/* Hàng 1: Âm thanh thịnh hành */}
        <div className="rounded-xl border border-border bg-card/60 p-3 overflow-hidden backdrop-blur-xs">
          <InfiniteMarquee speed="normal">
            {TRENDING_AUDIOS.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg border border-border/80 bg-background/80 hover:border-primary/40 transition-colors shrink-0"
              >
                <div className="size-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                  <Music2 className="size-4" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-foreground">{item.title}</div>
                  <div className="text-[10px] text-muted-foreground font-mono">
                    {item.author} • {item.plays} lượt dùng
                  </div>
                </div>
                <SoundEqualizer isPlaying={true} height={12} colorClass="bg-primary/80" />
              </div>
            ))}
          </InfiniteMarquee>
        </div>

        {/* Hàng 2: Hashtag thịnh hành chạy ngược chiều */}
        <div className="rounded-xl border border-border bg-card/60 p-3 overflow-hidden backdrop-blur-xs">
          <InfiniteMarquee speed="fast" reverse={true}>
            {TRENDING_TAGS.map((tag, idx) => (
              <span
                key={idx}
                className="px-3 py-1.5 rounded-full text-xs font-medium border border-border bg-background hover:border-primary/50 text-foreground transition-all cursor-pointer hover:text-primary shrink-0"
              >
                {tag}
              </span>
            ))}
          </InfiniteMarquee>
        </div>
      </section>

      {/* 5. Nền Mạng Lưới Hạt Sao Tương Tác (Particle Constellation Canvas) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cpu className="size-5 text-primary" />
            <h2 className="text-lg font-bold text-foreground">Mạng Lưới Hạt Sao Tương Tác (Particle Constellation)</h2>
          </div>
          <span className="text-xs text-muted-foreground">60 FPS Canvas 2D • Tương tác hút theo con trỏ chuột</span>
        </div>

        <div className="relative h-64 rounded-2xl border border-border bg-card overflow-hidden flex items-center justify-center text-center p-6 shadow-inner">
          <ParticleConstellationCanvas
            particleCount={45}
            maxDistance={120}
            particleColor="rgba(43, 111, 184, 0.55)"
            lineColor="rgba(43, 111, 184, 0.14)"
          />
          <div className="relative z-10 max-w-md space-y-2 pointer-events-none select-none">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-background/80 border border-border text-xs font-medium text-primary backdrop-blur-md shadow-xs">
              <Zap className="size-3.5 fill-current" />
              <span>Canvas 2D Tăng Tốc Phần Cứng</span>
            </div>
            <h3 className="text-lg font-bold text-foreground">Không Gian Kết Nối Sáng Tạo</h3>
            <p className="text-xs text-muted-foreground">
              Rê chuột xung quanh vùng này để thấy các hạt ánh sáng liên kết và hướng về con trỏ chuột trong thời gian thực.
            </p>
          </div>
        </div>
      </section>

      {/* 6. Hệ Thống Nút Bấm Sang Trọng (Shimmer Buttons & Badges) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="size-5 text-primary" />
            <h2 className="text-lg font-bold text-foreground">Nút Bấm & Huy Hiệu Sang Trọng (Shimmer Buttons)</h2>
          </div>
          <span className="text-xs text-muted-foreground">Dải lụa sáng quét qua tự động</span>
        </div>

        <div className="p-6 rounded-2xl border border-border bg-card flex flex-wrap items-center gap-4">
          <ShimmerButton onClick={handleConfetti} variant="primary">
            <Sparkles className="size-4" />
            <span>Xuất bản TikTok & Bắn pháo hoa</span>
          </ShimmerButton>

          <ShimmerButton variant="secondary">
            <Film className="size-4" />
            <span>Khởi tạo Studio AI</span>
          </ShimmerButton>

          <ShimmerButton variant="outline">
            <RotateCcw className="size-4" />
            <span>Làm mới tiến trình</span>
          </ShimmerButton>

          <button
            disabled
            className="px-4 py-2 rounded-lg border border-border bg-muted text-muted-foreground text-sm font-medium opacity-50 cursor-not-allowed"
          >
            Nút đang vô hiệu hóa
          </button>

          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs text-muted-foreground">Trạng thái phát sóng:</span>
            <StatusBeacon status="processing" size="md" />
            <StatusBeacon status="queued" size="md" />
            <StatusBeacon status="completed" size="md" />
            <StatusBeacon status="failed" size="md" />
          </div>
        </div>
      </section>
    </div>
  );
}

"use client";

import * as React from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Play,
  Heart,
  MessageCircle,
  Share2,
  TrendingUp,
  MoreVertical,
  Sparkles,
  Search,
  Bookmark,
  ExternalLink,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ContentItem } from "@/types";

interface ContentCardProps {
  content: ContentItem;
  onSave?: (id: string) => void;
  onGenerateIdea?: (content: ContentItem) => void;
}

export function ContentCard({ content, onSave, onGenerateIdea }: ContentCardProps) {
  const router = useRouter();

  const formatNum = (num?: number | null) => {
    if (num == null) return "?";
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  const getBadgeStyle = (badge: string) => {
    switch (badge) {
      case "trending":
        return "bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30";
      case "high_engagement":
        return "bg-teal-500/15 text-teal-600 dark:text-teal-400 border-teal-500/30";
      case "fast_growth":
        return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30";
      case "evergreen":
        return "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  const getBadgeLabel = (badge: string) => {
    switch (badge) {
      case "trending":
        return "Xu Hướng";
      case "high_engagement":
        return "Tương Tác Cao";
      case "fast_growth":
        return "Tăng Nhanh";
      case "evergreen":
        return "Nội Dung Bền Vững";
      default:
        return badge;
    }
  };

  return (
    <div className="group flex flex-col rounded-2xl border border-border/70 bg-card hover:border-primary/50 transition-all duration-200 overflow-hidden shadow-xs hover:shadow-md">
      {/* 9:16 Thumbnail Container with Overlay Information */}
      <div className="relative aspect-[9/13] w-full overflow-hidden bg-muted/80">
        {content.thumbnailUrl ? (
          <img src={content.thumbnailUrl} alt={content.title} className="size-full object-cover group-hover:scale-105 transition-transform duration-300" loading="lazy" />
        ) : (
          <div className="size-full flex items-center justify-center text-muted-foreground">
            <Play className="size-8" aria-hidden="true" />
          </div>
        )}

        {/* Gradient backdrop */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-black/40" />

        {/* Badges on Top */}
        <div className="absolute top-2.5 left-2.5 right-2.5 flex items-center justify-between gap-1 z-10">
          <div className="flex flex-wrap gap-1">
            {content.badges.map((b) => (
              <Badge
                key={b}
                variant="outline"
                className={`text-[10px] font-semibold px-2 py-0.5 backdrop-blur-md ${getBadgeStyle(b)}`}
              >
                {getBadgeLabel(b)}
              </Badge>
            ))}
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="size-7 rounded-full bg-black/40 hover:bg-black/60 text-white backdrop-blur-md"
              >
                <MoreVertical className="size-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48 rounded-xl shadow-lg">
              <DropdownMenuItem
                onClick={() => router.push(`/discover/${content.id}`)}
                className="text-xs font-medium cursor-pointer"
              >
                <Search className="size-3.5 mr-2" />
                Bóc tách chi tiết (Analyze)
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => router.push(`/ideas/generate?source=${content.id}`)}
                className="text-xs font-medium cursor-pointer text-primary"
              >
                <Sparkles className="size-3.5 mr-2" />
                Sinh ý tưởng tương tự
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onSave?.(content.id)}
                className="text-xs font-medium cursor-pointer"
              >
                <Bookmark className="size-3.5 mr-2" />
                Lưu vào thư viện nghiên cứu
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Middle Play Action */}
        <Link
          href={`/discover/${content.id}`}
          className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10"
        >
          <div className="size-11 rounded-full bg-primary/90 text-primary-foreground flex items-center justify-center shadow-lg transform group-hover:scale-110 transition-transform">
            <Play className="size-5 fill-current ml-0.5" />
          </div>
        </Link>

        {/* Bottom Overlay with Real TikTok Metrics */}
        <div className="absolute bottom-2.5 left-2.5 right-2.5 text-white z-10 space-y-1">
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="flex items-center gap-1 text-white">
              {content.channelAvatar ? <img src={content.channelAvatar} alt={content.channelName} className="size-5 rounded-full object-cover border border-white/40" /> : null}
              <span className="truncate max-w-[120px]">{content.channelName || "?"}</span>
            </span>
            <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-black/50 backdrop-blur-xs text-amber-300">
              {content.durationSec ? `${content.durationSec}s` : "?"}
            </span>
          </div>

          <div className="flex items-center justify-between text-[11px] pt-1 border-t border-white/20 font-mono">
            <span className="flex items-center gap-1 font-bold">
              {formatNum(content.metrics?.views)} views
            </span>
            <span className="flex items-center gap-1 text-emerald-300">
              <Zap className="size-3" />
              {content.growthVelocity || "?"}
            </span>
          </div>
        </div>
      </div>

      {/* Content Details */}
      <div className="p-3.5 flex-1 flex flex-col justify-between space-y-3">
        <div className="space-y-1.5">
          <Link
            href={`/discover/${content.id}`}
            className="font-semibold text-xs text-foreground line-clamp-2 hover:text-primary transition-colors leading-snug"
          >
            {content.title}
          </Link>

          <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
            {content.caption}
          </p>
        </div>

        {/* Evidence & Signal Tags */}
        <div className="space-y-2 pt-2 border-t border-border/50 text-[11px]">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground truncate">Chủ đề:</span>
            <Badge variant="secondary" className="text-[10px] font-medium truncate max-w-[150px]">
              {content.detectedTopic}
            </Badge>
          </div>

          <div className="flex items-center justify-between text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <ShieldCheck className="size-3 text-primary" />
              {content.evidence?.length ?? 0} Bằng chứng
            </span>
            <span className="font-medium text-primary">
              ER: {content.metrics?.engagementRate == null ? "—" : `${content.metrics.engagementRate}%`}
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="grid grid-cols-2 gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/discover/${content.id}`)}
            className="h-8 text-xs font-medium rounded-lg hover:border-primary hover:text-primary"
          >
            <Search className="size-3 mr-1" />
            Bóc tách
          </Button>

          <Button
            size="sm"
            onClick={() => router.push(`/ideas/generate?source=${content.id}`)}
            className="h-8 text-xs font-semibold rounded-lg bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground border border-primary/20 transition-all"
          >
            <Sparkles className="size-3 mr-1" />
            Tạo ý tưởng
          </Button>
        </div>
      </div>
    </div>
  );
}

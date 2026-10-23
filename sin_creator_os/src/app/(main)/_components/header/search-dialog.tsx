"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Lightbulb,
  Sparkles,
  FileText,
  Upload,
  Calendar,
  Compass,
  Video,
  BarChart3,
  Users,
  AtSign,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";

export function SearchDialog() {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const router = useRouter();

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const handleSelect = (url: string) => {
    setOpen(false);
    setQuery("");
    router.push(url);
  };

  return (
    <>
      <Button
        onClick={() => setOpen(true)}
        variant="outline"
        size="sm"
        className="h-8 w-44 md:w-64 justify-between rounded-lg border-border/60 bg-muted/30 px-2.5 text-xs text-muted-foreground hover:bg-muted/60 hover:text-foreground font-normal"
      >
        <span className="flex items-center gap-2 truncate">
          <Search className="size-3.5 text-muted-foreground" />
          <span className="truncate">Tìm kiếm vạn năng...</span>
        </span>
        <kbd className="hidden sm:inline-flex h-4 items-center gap-0.5 rounded border border-border/80 bg-background px-1 font-mono text-[10px] text-muted-foreground">
          <span className="text-[9px]">Ctrl+</span>K
        </kbd>
      </Button>

      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput
          placeholder="Tìm kịch bản, ý tưởng, video, hashtag (#), kênh (@)..."
          value={query}
          onValueChange={setQuery}
        />
        <CommandList className="max-h-96">
          <CommandEmpty>Không tìm thấy kết quả phù hợp.</CommandEmpty>

          <CommandGroup heading="Thao Tác Nhanh (Quick Actions)">
            <CommandItem
              onSelect={() => handleSelect("/ideas/generate")}
              className="flex items-center gap-2 cursor-pointer text-primary font-medium"
            >
              <Sparkles className="size-4" />
              <span>Sinh ý tưởng mới bằng AI</span>
            </CommandItem>
            <CommandItem
              onSelect={() => handleSelect("/scripts/script_01")}
              className="flex items-center gap-2 cursor-pointer"
            >
              <FileText className="size-4" />
              <span>Soạn kịch bản TikTok chuẩn 5 block</span>
            </CommandItem>
            <CommandItem
              onSelect={() => handleSelect("/media")}
              className="flex items-center gap-2 cursor-pointer"
            >
              <Upload className="size-4" />
              <span>Tải video tư liệu lên thư viện</span>
            </CommandItem>
            <CommandItem
              onSelect={() => handleSelect("/publishing")}
              className="flex items-center gap-2 cursor-pointer"
            >
              <Calendar className="size-4" />
              <span>Lên lịch xuất bản bài đăng</span>
            </CommandItem>
          </CommandGroup>

          <CommandSeparator />

          <CommandGroup heading="Các Phân Hệ Chính">
            <CommandItem onSelect={() => handleSelect("/dashboard")} className="cursor-pointer">
              <BarChart3 className="size-4 mr-2" /> Creator Dashboard
            </CommandItem>
            <CommandItem onSelect={() => handleSelect("/discover")} className="cursor-pointer">
              <Compass className="size-4 mr-2" /> Khám Phá Nội Dung & Xu Hướng (Discover)
            </CommandItem>
            <CommandItem onSelect={() => handleSelect("/ideas")} className="cursor-pointer">
              <Lightbulb className="size-4 mr-2" /> Phòng Lab Ý Tưởng (Idea Lab)
            </CommandItem>
            <CommandItem onSelect={() => handleSelect("/ai-studio")} className="cursor-pointer">
              <Sparkles className="size-4 mr-2" /> AI Studio (Tools & Voice)
            </CommandItem>
            <CommandItem onSelect={() => handleSelect("/video-studio")} className="cursor-pointer">
              <Video className="size-4 mr-2" /> Video Studio (Dựng Video Dọc 9:16)
            </CommandItem>
            <CommandItem onSelect={() => handleSelect("/trends")} className="cursor-pointer">
              <TrendingUp className="size-4 mr-2" /> Radar Bắt Xu Hướng (Trends)
            </CommandItem>
            <CommandItem onSelect={() => handleSelect("/competitors")} className="cursor-pointer">
              <Users className="size-4 mr-2" /> Theo Dõi Đối Thủ (Competitors)
            </CommandItem>
            <CommandItem onSelect={() => handleSelect("/channels")} className="cursor-pointer">
              <AtSign className="size-4 mr-2" /> Quản Lý Kênh TikTok (Channels)
            </CommandItem>
          </CommandGroup>

          <CommandSeparator />

          <CommandGroup heading="Kịch Bản & Ý Tưởng Gần Đây">
            <CommandItem onSelect={() => handleSelect("/scripts/script_01")} className="cursor-pointer">
              <FileText className="size-4 mr-2 text-primary" /> Lộ Trình Tự Động Hóa Kênh TikTok Từ Con Số 0
            </CommandItem>
            <CommandItem onSelect={() => handleSelect("/ideas")} className="cursor-pointer">
              <Lightbulb className="size-4 mr-2 text-amber-500" /> Công Thức Viết Hook 3 Giây Chuyển Đổi Cao
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}

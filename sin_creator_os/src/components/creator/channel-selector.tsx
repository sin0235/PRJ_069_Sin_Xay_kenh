"use client";

import * as React from "react";
import { Check, ChevronsUpDown, Smartphone } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useCreatorStore } from "@/stores/use-creator-store";
import { TikTokService } from "@/services/tiktok-service";

export function ChannelSelector() {
  const { channels, setChannels, activeChannelId, setActiveChannelId } = useCreatorStore();

  React.useEffect(() => {
    TikTokService.getConnectedChannels().then(setChannels).catch(() => setChannels([]));
  }, [setChannels]);

  const activeChannel = channels.find((c) => c.id === activeChannelId) || channels[0];
  const formatFollowers = (count: number | null | undefined) => {
    if (count == null) return "";
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
    return count.toString();
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-2 rounded-lg border-border/60 hover:border-border font-medium text-xs px-2.5 bg-background/80"
        >
          <Avatar className="size-5 border border-primary/20">
            <AvatarImage src={activeChannel?.avatarUrl || undefined} alt={activeChannel?.username || ""} />
            <AvatarFallback className="text-[10px] bg-primary/10 text-primary">
              {activeChannel?.username ? activeChannel.username.slice(1, 3).toUpperCase() : <Smartphone className="size-3" aria-hidden="true" />}
            </AvatarFallback>
          </Avatar>
          <span className="max-w-[120px] truncate text-foreground font-semibold">
            {activeChannel?.username || "Chưa kết nối kênh"}
          </span>
          {formatFollowers(activeChannel?.followersCount) && (
            <span className="text-[10px] text-muted-foreground font-normal hidden sm:inline-block">
              {formatFollowers(activeChannel.followersCount)}
            </span>
          )}
          <ChevronsUpDown className="size-3 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-64 rounded-xl shadow-lg border-border/80" align="end">
        <DropdownMenuLabel className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-1.5 flex items-center justify-between">
          <span>Kênh TikTok Đang Chọn</span>
          <span className="text-muted-foreground font-semibold">
            {activeChannel?.status === "connected" ? "Đã kết nối" : activeChannel ? "Cần kết nối lại" : "Chưa có kênh"}
          </span>
        </DropdownMenuLabel>
        {channels.length === 0 && (
          <DropdownMenuItem disabled className="text-xs text-muted-foreground">
            Chưa có kênh TikTok được kết nối.
          </DropdownMenuItem>
        )}
        {channels.map((chan) => (
          <DropdownMenuItem
            key={chan.id}
            onClick={() => setActiveChannelId(chan.id)}
            className="flex items-center justify-between px-3 py-2 cursor-pointer rounded-lg hover:bg-muted"
          >
            <div className="flex items-center gap-2.5">
              <Avatar className="size-7 border border-border">
                <AvatarImage src={chan.avatarUrl} alt={chan.username} />
                <AvatarFallback className="text-xs bg-muted">
                  {chan.username.slice(1, 3).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="flex flex-col">
                <span className="font-semibold text-xs text-foreground">{chan.username}</span>
                <span className="text-[11px] text-muted-foreground">
                  {formatFollowers(chan.followersCount) || "—"} • {chan.status === "connected" ? "Đã kết nối" : chan.status === "expired" ? "Cần kết nối lại" : "Chưa khả dụng"}
                </span>
              </div>
            </div>
            {activeChannelId === chan.id && <Check className="size-4 text-primary" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => window.location.href = "/channels"}
          className="flex items-center gap-2 px-3 py-2 text-xs text-primary font-medium cursor-pointer rounded-lg hover:bg-primary/5"
        >
          <Smartphone className="size-3.5" />
          Quản lý hoặc kết nối kênh mới
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

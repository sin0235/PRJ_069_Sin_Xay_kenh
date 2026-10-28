"use client";

import { Sparkles } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

export function AIJobIndicator() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-2 rounded-lg text-xs">
          <Sparkles className="size-3.5" aria-hidden="true" />
          <span>T?c v? AI</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-80 rounded-xl p-2" align="end">
        <DropdownMenuLabel className="text-xs">L?ch s? t?c v? AI</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <p className="px-2 py-4 text-center text-xs text-muted-foreground">
          Chưa có dữ liệu tác vụ từ máy chủ.
        </p>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

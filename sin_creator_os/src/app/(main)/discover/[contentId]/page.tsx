"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

export default function ContentAnalysisPage() {
  const router = useRouter();
  return (
    <div className="space-y-4 p-6">
      <Button variant="outline" size="sm" onClick={() => router.push("/discover")}>
        <ArrowLeft className="mr-2 size-4" aria-hidden="true" /> Quay lại thư viện
      </Button>
      <Empty className="min-h-80 border">
        <EmptyHeader>
          <EmptyMedia variant="icon"><Search aria-hidden="true" /></EmptyMedia>
          <EmptyTitle>Chưa có báo cáo phân tích</EmptyTitle>
          <EmptyDescription>H? th?ng ch?a c? k?t qu? ph?n t?ch th?t cho t? li?u n?y.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    </div>
  );
}

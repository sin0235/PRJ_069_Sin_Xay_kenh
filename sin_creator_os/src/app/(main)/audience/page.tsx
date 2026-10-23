"use client";

import * as React from "react";
import { Users, PieChart as PieIcon, MapPin, Clock, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

const ageDemographics = [
  { bracket: "18 - 24 tuổi", percentage: 48 },
  { bracket: "25 - 34 tuổi", percentage: 34 },
  { bracket: "35 - 44 tuổi", percentage: 12 },
  { bracket: "45+ tuổi", percentage: 6 },
];

const topLocations = [
  { city: "Hồ Chí Minh", percentage: 44 },
  { city: "Hà Nội", percentage: 32 },
  { city: "Đà Nẵng", percentage: 11 },
  { city: "Khác", percentage: 13 },
];

const activeHours = [
  { time: "11:30 - 13:00 (Nghỉ trưa)", level: "Cao điểm" },
  { time: "19:00 - 21:30 (Khung giờ vàng)", level: "Đỉnh điểm" },
  { time: "22:00 - 23:30 (Lướt đêm)", level: "Tương tác tốt" },
];

export default function AudiencePage() {
  return (
    <div className="space-y-6 pb-20">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Chân Dung Khán Giả (Audience Insights)
          </h1>
          <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
            Follower Persona
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">
          Hiểu rõ độ tuổi, vị trí địa lý và hành vi trực tuyến để may đo nội dung chính xác.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Age Groups */}
        <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4">
          <div>
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <Users className="size-4 text-primary" /> Độ Tuổi Người Xem
            </CardTitle>
            <CardDescription className="text-xs">Tập trung lớn ở nhóm Gen Z và Millennials</CardDescription>
          </div>

          <div className="space-y-3">
            {ageDemographics.map((age) => (
              <div key={age.bracket} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="font-medium text-foreground">{age.bracket}</span>
                  <span className="font-bold text-primary font-mono">{age.percentage}%</span>
                </div>
                <Progress value={age.percentage} className="h-2" />
              </div>
            ))}
          </div>
        </Card>

        {/* Locations */}
        <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4">
          <div>
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <MapPin className="size-4 text-primary" /> Vị Trí Địa Lý
            </CardTitle>
            <CardDescription className="text-xs">Các tỉnh thành có lượng xem cao nhất</CardDescription>
          </div>

          <div className="space-y-3">
            {topLocations.map((loc) => (
              <div key={loc.city} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="font-medium text-foreground">{loc.city}</span>
                  <span className="font-bold text-emerald-600 font-mono">{loc.percentage}%</span>
                </div>
                <Progress value={loc.percentage} className="h-2" />
              </div>
            ))}
          </div>
        </Card>

        {/* Active Hours */}
        <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4">
          <div>
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <Clock className="size-4 text-primary" /> Khung Giờ Hoạt Động
            </CardTitle>
            <CardDescription className="text-xs">Thời điểm vàng để đăng bài tối ưu reach</CardDescription>
          </div>

          <div className="space-y-2.5">
            {activeHours.map((h) => (
              <div key={h.time} className="p-3 rounded-xl border border-border/60 bg-muted/20 flex items-center justify-between text-xs">
                <span className="font-semibold text-foreground font-mono">{h.time}</span>
                <Badge variant="outline" className="text-[10px] border-primary/30 text-primary bg-primary/5">
                  {h.level}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

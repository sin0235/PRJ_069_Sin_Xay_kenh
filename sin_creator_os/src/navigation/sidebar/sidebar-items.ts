import {
  Compass,
  Home,
  Lightbulb,
  Sparkles,
  Video,
  Kanban,
  Calendar,
  FolderOpen,
  Send,
  BarChart3,
  Users,
  Flame,
  AtSign,
  UserPlus,
  Plug,
  Settings,
  type LucideIcon,
  PieChart,
} from "lucide-react";

export type NavBadge = "new" | "ai" | "pro" | "soon";

export interface NavSubItem {
  id: string;
  title: string;
  url: string;
  icon?: LucideIcon;
  badge?: NavBadge;
  disabled?: boolean;
  newTab?: boolean;
}

interface NavItemBase {
  id: string;
  title: string;
  icon?: LucideIcon;
  badge?: NavBadge;
  disabled?: boolean;
  newTab?: boolean;
}

export interface NavMainLinkItem extends NavItemBase {
  url: string;
  subItems?: never;
}

export interface NavMainParentItem extends NavItemBase {
  subItems: NavSubItem[];
}

export type NavMainItem = NavMainLinkItem | NavMainParentItem;

export interface NavGroup {
  id: number;
  label?: string;
  items: NavMainItem[];
}

export const sidebarItems: NavGroup[] = [
  {
    id: 1,
    label: "Sáng Tạo",
    items: [
      {
        id: "home",
        title: "Tổng quan",
        url: "/dashboard",
        icon: Home,
      },
      {
        id: "discover",
        title: "Khám phá xu hướng",
        url: "/discover",
        icon: Compass,
        badge: "new",
      },
      {
        id: "ideas",
        title: "Kho ý tưởng",
        url: "/ideas",
        icon: Lightbulb,
      },
      {
        id: "ai-studio",
        title: "Studio AI",
        url: "/ai-studio",
        icon: Sparkles,
        badge: "ai",
      },
      {
        id: "video-studio",
        title: "Phòng dựng Video",
        url: "/video-studio",
        icon: Video,
      },
    ],
  },
  {
    id: 2,
    label: "Quản Lý",
    items: [
      {
        id: "content",
        title: "Quy trình nội dung",
        url: "/content",
        icon: Kanban,
      },
      {
        id: "calendar",
        title: "Lịch nội dung",
        url: "/calendar",
        icon: Calendar,
      },
      {
        id: "media",
        title: "Thư viện tư liệu",
        url: "/media",
        icon: FolderOpen,
      },
      {
        id: "publishing",
        title: "Lên lịch & Đăng bài",
        url: "/publishing",
        icon: Send,
      },
    ],
  },
  {
    id: 3,
    label: "Phân Tích",
    items: [
      {
        id: "analytics",
        title: "Hiệu suất kênh",
        url: "/analytics",
        icon: BarChart3,
      },
      {
        id: "competitors",
        title: "Theo dõi đối thủ",
        url: "/competitors",
        icon: Users,
      },
      {
        id: "audience",
        title: "Chân dung khán giả",
        url: "/audience",
        icon: PieChart,
      },
      {
        id: "trends",
        title: "Xu hướng thịnh hành",
        url: "/trends",
        icon: Flame,
      },
    ],
  },
  {
    id: 4,
    label: "Không Gian Làm Việc",
    items: [
      {
        id: "channels",
        title: "Kênh TikTok",
        url: "/channels",
        icon: AtSign,
      },
      {
        id: "team",
        title: "Đội ngũ & Phân quyền",
        url: "/team",
        icon: UserPlus,
      },
      {
        id: "integrations",
        title: "Kết nối & Tích hợp",
        url: "/settings/integrations",
        icon: Plug,
      },
      {
        id: "settings",
        title: "Cài đặt hệ thống",
        url: "/settings",
        icon: Settings,
      },
    ],
  },
];

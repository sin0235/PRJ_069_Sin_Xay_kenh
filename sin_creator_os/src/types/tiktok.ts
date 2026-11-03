export interface TikTokChannel {
  id: string;
  username: string;
  displayName: string;
  avatarUrl: string;
  bio: string;
  followersCount: number;
  followingCount: number;
  likesCount: number;
  videoCount: number;
  engagementRate: number;
  connectedAt: string;
  status: 'connected' | 'expired' | 'error';
  niche: string;
  primaryAudience: string;
  region: string;
}

export interface ChannelMetricPoint {
  date: string;
  views: number;
  followers: number;
  engagementRate: number;
  watchTimeSec: number;
  completionRate: number;
}

export interface AudienceDemographic {
  ageGroups: { bracket: string; percentage: number }[];
  genderSplit: { male: number; female: number; other: number };
  topLocations: { country: string; percentage: number }[];
  activeHours: { hour: number; activityLevel: number }[];
}

export interface ChannelKPIs {
  followers: { value: number; changePercent: number };
  views: { value: number; changePercent: number };
  engagement: { value: number; changePercent: number };
  posts: { value: number; changePercent: number };
  avgWatchTime: { value: number; changePercent: number };
  growthRate: { value: number; changePercent: number };
}

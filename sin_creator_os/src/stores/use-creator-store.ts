import { create } from 'zustand';
import { TikTokChannel } from '@/types';

const DEFAULT_REAL_CHANNELS: TikTokChannel[] = [];

interface CreatorState {
  currentWorkspace: string;
  channels: TikTokChannel[];
  activeChannelId: string;
  isCreateModalOpen: boolean;
  createModalInitialTab: 'idea' | 'script' | 'video' | 'schedule';
  activeJobsCount: number;
  
  // Actions
  setWorkspace: (ws: string) => void;
  setChannels: (channels: TikTokChannel[]) => void;
  setActiveChannelId: (id: string) => void;
  openCreateModal: (tab?: 'idea' | 'script' | 'video' | 'schedule') => void;
  closeCreateModal: () => void;
  setActiveJobsCount: (count: number) => void;
}

export const useCreatorStore = create<CreatorState>((set) => ({
  currentWorkspace: 'default_ws',
  channels: DEFAULT_REAL_CHANNELS,
  activeChannelId: '',
  isCreateModalOpen: false,
  createModalInitialTab: 'idea',
  activeJobsCount: 0,
  
  setWorkspace: (ws) => set({ currentWorkspace: ws }),
  setChannels: (channels) => set({ channels, activeChannelId: channels[0]?.id || '' }),
  setActiveChannelId: (id) => set({ activeChannelId: id }),
  openCreateModal: (tab = 'idea') => set({ isCreateModalOpen: true, createModalInitialTab: tab }),
  closeCreateModal: () => set({ isCreateModalOpen: false }),
  setActiveJobsCount: (count) => set({ activeJobsCount: count }),
}));

import { create } from 'zustand';
import { TikTokChannel } from '@/types';

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
  currentWorkspace: 'b6102190-1f6f-5624-bfb8-2e1091fa2560',
  channels: [],
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

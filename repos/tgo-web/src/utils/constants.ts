
import type { NavigationItem } from '@/types';

// Navigation items configuration
export const NAVIGATION_ITEMS: NavigationItem[] = [
  {
    id: 'chat',
    title: 'navigation.chat',
    icon: 'MessageCircle',
    path: '/chat'
  },
  {
    id: 'ai',
    title: 'navigation.ai',
    icon: 'Sparkles',
    path: '/ai'
  },
  {
    id: 'visitors',
    title: 'navigation.visitors',
    icon: 'Users',
    path: '/visitors'
  },
  {
    id: 'knowledge',
    title: 'navigation.knowledge',
    icon: 'Library',
    path: '/knowledge'
  },
  {
    id: 'channels',
    title: 'navigation.channels',
    icon: 'Platform',
    path: '/platforms'
  },
  {
    id: 'settings',
    title: 'navigation.settings',
    icon: 'Settings',
    path: '/settings'
  }
];

// AI功能菜单配置
export const AI_MENU_ITEMS: NavigationItem[] = [
  {
    id: 'agents',
    title: 'navigation.agents',
    icon: 'Bot',
    path: '/ai/agents'
  },
  {
    id: 'tools',
    title: 'navigation.tools',
    icon: 'Wrench',
    path: '/ai/tools'
  },
  {
    id: 'workflows',
    title: 'navigation.workflows',
    icon: 'GitBranch',
    path: '/ai/workflows'
  },
  {
    id: 'store',
    title: 'navigation.store',
    icon: 'Brain',
    path: '/ai/store'
  }
];

// Platform icons mapping
export const PLATFORM_ICONS: Record<string, string> = {
  wechat: 'https://cdn.simpleicons.org/wechat/07C160',
  tiktok: 'https://cdn.simpleicons.org/tiktok/000000',
  website: 'Globe'
} as const;

// Message types
export const MESSAGE_TYPES = {
  VISITOR: 'visitor',
  AGENT: 'agent',
  SYSTEM: 'system'
} as const;

// Tag colors mapping
export const TAG_COLORS: Record<string, string> = {
  '新用户': 'bg-blue-100 text-blue-700',
  '来自搜索': 'bg-gray-100 text-gray-700',
  '来自官网': 'bg-gray-100 text-gray-700',
  '咨询产品A': 'bg-green-100 text-green-700',
  '老客户': 'bg-purple-100 text-purple-700',
  '技术支持': 'bg-indigo-100 text-indigo-700',
  '待跟进': 'bg-yellow-100 text-yellow-700',
  '投诉': 'bg-red-100 text-red-700',
  '高优先级': 'bg-pink-100 text-pink-700',
  '咨询售前': 'bg-gray-100 text-gray-700'
} as const;

// Avatar placeholder URLs
export const AVATAR_URLS: Record<string, string> = {
  user: 'https://i.pravatar.cc/40?img=0',
  visitor: 'https://i.pravatar.cc/64?img=30'
} as const;

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import DOMPurify from 'dompurify';
import Icon from '@/components/ui/Icon';
import Pagination from '@/components/ui/Pagination';
import { useTranslation } from 'react-i18next';
import { searchApiService, type SearchRequestParams } from '@/services/searchApi';
import type {
  SearchScope,
  UnifiedSearchResponse,
  VisitorBasicResponse,
  MessageSearchResult,
  ChannelVisitorExtra,
  ChannelInfo,
  Chat,
} from '@/types';
import { PlatformType } from '@/types';
import { useToast } from '@/hooks/useToast';
import { showApiError } from '@/utils/toastHelpers';
import { useChatStore } from '@/stores/chatStore';
import { CHAT_PRIORITY, CHAT_STATUS, DEFAULT_CHANNEL_TYPE, VISITOR_STATUS } from '@/constants';
import { getChannelKey } from '@/utils/channelUtils';
import { ChatAvatar } from '@/components/chat/ChatAvatar';
import { ChatPlatformIcon } from '@/components/chat/ChatPlatformIcon';
import { toPlatformType } from '@/utils/platformUtils';
import { useChannelDisplay } from '@/hooks/useChannelDisplay';

const parseMinutesAgo = (timestamp?: string): number | undefined => {
  if (!timestamp) return undefined;
  // Normalize: replace space with T, limit fractional seconds to 3 digits
  let normalized = timestamp.replace(' ', 'T').replace(/(\.\d{3})\d+$/, '$1');
  // If no timezone info, assume UTC and append 'Z'
  if (!/[Zz]$/.test(normalized) && !/[+-]\d{2}:\d{2}$/.test(normalized)) {
    normalized += 'Z';
  }
  let ms = Date.parse(normalized);
  if (!Number.isFinite(ms)) {
    // Fallback: drop fractional seconds entirely, still assume UTC
    normalized = timestamp.replace(' ', 'T').split('.')[0] + 'Z';
    ms = Date.parse(normalized);
  }
  if (!Number.isFinite(ms)) return undefined;
  const minutes = Math.floor((Date.now() - ms) / 60000);
  return Math.max(0, minutes);
};

export interface SearchPanelProps {
  open: boolean;
  onClose: () => void;
}

// Tabs are defined inside component to access i18n translations

const SearchPanel: React.FC<SearchPanelProps> = ({ open, onClose }) => {
  const { showToast } = useToast();
  const [query, setQuery] = useState('');
  const [activeTab, setActiveTab] = useState<SearchScope>('all');
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<UnifiedSearchResponse | null>(null);

  const [visitorPage, setVisitorPage] = useState(1);
  const [messagePage, setMessagePage] = useState(1);

  const [accumulatedVisitors, setAccumulatedVisitors] = useState<VisitorBasicResponse[]>([]);
  const [hasMoreVisitors, setHasMoreVisitors] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const visitorObserverRef = useRef<IntersectionObserver | null>(null);
  const visitorSentinelRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<any>(null);
  const { t } = useTranslation();

  const tabs = useMemo(() => (
    [
      { key: 'all' as SearchScope, label: t('search.tabs.all', '所有'), icon: 'Grid' },
      { key: 'visitors' as SearchScope, label: t('search.tabs.visitors', '访客'), icon: 'Users' },
      { key: 'messages' as SearchScope, label: t('search.tabs.messages', '消息'), icon: 'MessageSquareText' },
    ]
  ), [t]);

  // Autofocus when open
  useEffect(() => {
    if (open) {
      // reset state when opening
      setError(null);
      setLoading(false);
      setLoadingMore(false);
      // Focus input
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setData(null);
      setQuery('');
      setVisitorPage(1);
      setMessagePage(1);
      setAccumulatedVisitors([]);
      setHasMoreVisitors(false);
      setActiveTab('all');
    }
  }, [open]);

  // Reset pages and accumulated data when query or tab changes
  useEffect(() => {
    setVisitorPage(1);
    setMessagePage(1);
    setAccumulatedVisitors([]);
    setHasMoreVisitors(false);
  }, [query, activeTab]);

  // Close on ESC
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  // Click outside to close
  const handleBackdropClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  }, [onClose]);

  const doSearch = useCallback(async (params: SearchRequestParams, isLoadMore = false) => {
    if (isLoadMore) {
      setLoadingMore(true);
    } else {
      setLoading(true);
    }
    setError(null);
    try {
      const resp = await searchApiService.unifiedSearch(params);
      setData(resp);

      if (params.scope === 'all') {
        setAccumulatedVisitors(resp.visitors);
        setHasMoreVisitors(resp.visitor_pagination?.has_next ?? false);
      } else if (params.scope === 'visitors') {
        if (params.visitor_page === 1) {
          setAccumulatedVisitors(resp.visitors);
        } else {
          setAccumulatedVisitors(prev => [...prev, ...resp.visitors]);
        }
        setHasMoreVisitors(resp.visitor_pagination?.has_next ?? false);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : t('search.errorGeneric', '搜索失败，请稍后重试');
      setError(msg);
      showApiError(showToast, err);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [showToast, t]);

  // Infinite scroll for visitors
  useEffect(() => {
    if (activeTab !== 'visitors' || !hasMoreVisitors || loading || loadingMore) return;

    const options = {
      root: panelRef.current,
      rootMargin: '20px',
      threshold: 0.1
    };

    const callback: IntersectionObserverCallback = (entries) => {
      if (entries[0].isIntersecting) {
        setVisitorPage(p => p + 1);
      }
    };

    const observer = new IntersectionObserver(callback, options);
    visitorObserverRef.current = observer;
    
    const sentinel = visitorSentinelRef.current;
    if (sentinel) {
      observer.observe(sentinel);
    }

    return () => {
      if (observer) {
        observer.disconnect();
      }
    };
  }, [activeTab, hasMoreVisitors, loading, loadingMore]);

  // Debounced search on query or tab/page change
  useEffect(() => {
    if (!open) return;
    if (!query || query.trim().length === 0) {
      setData(null);
      setAccumulatedVisitors([]);
      setHasMoreVisitors(false);
      return;
    }

    const params: SearchRequestParams = {
      q: query.trim(),
      scope: activeTab,
      visitor_page: visitorPage,
      message_page: messagePage,
    };

    const isLoadMore = activeTab === 'visitors' && visitorPage > 1;

    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    
    if (isLoadMore) {
      // No debounce for pagination clicks/infinite scroll
      doSearch(params, true);
    } else {
      debounceTimerRef.current = setTimeout(() => doSearch(params), 300);
    }

    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [open, query, activeTab, visitorPage, messagePage, doSearch]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
  }, []);

  const handleClear = useCallback(() => {
    setQuery('');
    setData(null);
    setError(null);
    inputRef.current?.focus();
  }, []);

  const SearchMessageItem: React.FC<{ m: MessageSearchResult }> = ({ m }) => {
    const channelId = m.channel_id || undefined;
    const channelType = m.channel_type ?? DEFAULT_CHANNEL_TYPE;
    const isAgentChat = channelId?.endsWith('-agent') ?? false;
    const isTeamChat = channelId?.endsWith('-team') ?? false;

    const { name, avatar, extra } = useChannelDisplay({
      channelId,
      channelType,
      // Skip fetch for special chat types
      skipFetch: isAgentChat || isTeamChat,
    });

    const displayName = isAgentChat
      ? t('chat.header.agentFallback', 'AI员工')
      : isTeamChat
        ? t('chat.header.teamFallback', 'AI员工团队')
        : name;
    const displayAvatar = avatar;

    const visitorExtra = extra as ChannelVisitorExtra | undefined;
    const { visitorStatus, lastSeenMinutes } = useMemo((): { visitorStatus?: 'online' | 'offline' | 'away'; lastSeenMinutes?: number } => {
      if (visitorExtra?.is_online !== undefined) {
        if (visitorExtra.is_online) return { visitorStatus: 'online', lastSeenMinutes: undefined };
        const minutes = parseMinutesAgo(visitorExtra.last_offline_time) ?? 0;
        return { visitorStatus: 'offline', lastSeenMinutes: minutes };
      }
      return { visitorStatus: undefined, lastSeenMinutes: undefined };
    }, [visitorExtra?.is_online, visitorExtra?.last_offline_time]);

    const platformType: PlatformType | undefined = useMemo(() => {
      const extraObj: any = extra;
      const fromExtra: PlatformType | undefined =
        (extraObj && typeof extraObj === 'object' && 'platform_type' in extraObj) ? (extraObj.platform_type as PlatformType) : undefined;
      return fromExtra ?? (m.payload?.platform_type as PlatformType) ?? toPlatformType(m.topic?.split(':')[0] || '');
    }, [extra, m.payload, m.topic]);

    return (
      <button
        className="w-full flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 text-left transition-colors group"
        onClick={() => openConversation(channelId, channelType)}
      >
        <ChatAvatar
          displayName={displayName}
          displayAvatar={displayAvatar}
          visitorStatus={visitorStatus}
          lastSeenMinutes={lastSeenMinutes}
          colorSeed={channelId}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">{displayName}</span>
              <ChatPlatformIcon platformType={platformType} />
            </div>
            <span className="text-[10px] text-gray-400 dark:text-gray-500 whitespace-nowrap">
              {m.timestamp ? new Date(m.timestamp * 1000).toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              }) : ''}
            </span>
          </div>
          <p
            className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 leading-relaxed search-html"
            dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.preview_text || '') }}
          />
        </div>
        <Icon name="ChevronRight" size={16} className="text-gray-300 dark:text-gray-600 ml-2 mt-1 opacity-0 group-hover:opacity-100 transition-opacity" />
      </button>
    );
  };

  // 打开既有会话（按 channelId/channelType 查找）
  const openConversation = useCallback((channelId?: string | null, channelType?: number | null) => {
    const chatsStore = useChatStore.getState();
    if (!channelId) {
      showToast('info', t('search.toasts.notFoundTitle', '未找到会话'), t('search.toasts.noConversationInfo', '该结果缺少会话信息'));
      // Always close search panel after selecting a result
      onClose();
      return;
    }
    const type = channelType ?? DEFAULT_CHANNEL_TYPE;
    const chat = chatsStore.chats.find(c => c.channelId === channelId && c.channelType === type);
    if (chat) {
      chatsStore.setActiveChat(chat);
      onClose();
    } else {
      showToast('info', t('search.toasts.notFoundTitle', '未找到会话'), t('search.toasts.notInRecent', '该会话不在最近列表中，请尝试刷新'));
      // Still close the panel after click (UX expectation)
      onClose();
    }
  }, [onClose, showToast, t]);

  // 打开访客最近会话（若不存在则创建）
  const openVisitorConversation = useCallback((v: VisitorBasicResponse) => {
    const chatsStore = useChatStore.getState();
    try {
      const visitorId = v?.id;
      if (!visitorId) {
        showToast('warning', t('search.toasts.incompleteVisitorInfo', '访客信息不完整'), t('search.toasts.missingVisitorId', '缺少 visitor_id'));
        onClose();
        return;
      }
      const channelId = `${visitorId}-vtr`;
      const channelType = 251; // 访客会话类型

      // 1) 已存在则直接切换
      const exist = chatsStore.chats.find(c => c.channelId === channelId && c.channelType === channelType);
      if (exist) {
        chatsStore.setActiveChat(exist);
        onClose();
        return;
      }

      // 2) 不存在则新建 Chat 对象并插入到顶部
      const fallbackName = t('visitor.fallbackName', '访客 {{suffix}}').replace('{{suffix}}', v.platform_open_id.slice(-4));
      const rawName = (v.name || v.nickname || fallbackName) as string;
      const plainName = (rawName || '').replace(/<[^>]*>/g, '') || fallbackName;

      const key = getChannelKey(channelId, channelType);
      const nowIso = new Date().toISOString();
      const nowSec = Math.floor(Date.now() / 1000);

      const extra: ChannelVisitorExtra = {
        id: v.id,
        platform_id: v.platform_id,
        platform_type: (v.platform_type ?? PlatformType.WEBSITE),
        platform_open_id: v.platform_open_id,
        name: v.name || undefined,
        nickname: v.nickname || undefined,
        avatar_url: v.avatar_url || undefined,
        is_online: v.is_online,
        created_at: v.created_at,
        updated_at: v.updated_at,
        ai_disabled: v.ai_disabled ?? undefined,
      } as any;

      const channelInfo: ChannelInfo = {
        name: plainName,
        avatar: v.avatar_url || '',
        channel_id: channelId,
        channel_type: channelType,
        extra,
      };

      const newChat: Chat = {
        id: key,
        platform: (v.platform_type ?? PlatformType.WEBSITE) as unknown as string,
        lastMessage: '',
        timestamp: nowIso,
        lastTimestampSec: nowSec,
        status: CHAT_STATUS.ACTIVE,
        unreadCount: 0,
        channelId,
        channelType,
        lastMsgSeq: 0,
        channelInfo,
        tags: [],
        priority: CHAT_PRIORITY.NORMAL,
        visitorStatus: v.is_online ? VISITOR_STATUS.ONLINE : VISITOR_STATUS.OFFLINE,
      } as any;

      chatsStore.setChats([newChat, ...chatsStore.chats]);
      chatsStore.setActiveChat(newChat);
      onClose();
    } catch (e) {
      console.error('打开访客会话失败', e);
      showApiError(showToast, e);
      onClose();
    }
  }, [onClose, showToast, t]);

  const renderVisitorItem = useCallback((v: VisitorBasicResponse) => {
    const fallbackName = t('visitor.fallbackName', '访客 {{suffix}}').replace('{{suffix}}', v.platform_open_id.slice(-4));
    const rawName = (v.name || v.nickname || fallbackName) as string;
    const plainName = (rawName || '').replace(/<[^>]*>/g, '') || fallbackName;
    const nameHtml = DOMPurify.sanitize(rawName || '');
    const platformType: PlatformType = v.platform_type ?? PlatformType.WEBSITE;
    // Keep default avatar color consistent with conversation list (visitorId-vtr)
    const channelIdForColor = `${v.id}-vtr`;

    return (
      <button
        key={v.id}
        className="w-full flex items-center p-2 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600/50 text-left"
        onClick={() => openVisitorConversation(v)}
      >
        {/* Avatar - use same logic as ChatList */}
        <ChatAvatar displayName={plainName} displayAvatar={v.avatar_url || ''} visitorStatus={v.is_online ? 'online' : 'offline'} colorSeed={channelIdForColor} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center min-w-0">
            <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate search-html" dangerouslySetInnerHTML={{ __html: nameHtml }} />
            <ChatPlatformIcon platformType={platformType} />
          </div>
        </div>
        <Icon name="ChevronRight" size={16} className="text-gray-300 dark:text-gray-600" />
      </button>
    );
  }, [t, openVisitorConversation]);

  const renderMessageItem = useCallback((m: MessageSearchResult) => {
    return <SearchMessageItem m={m} />;
  }, [t, openConversation]);

  const messageTotalPages = useMemo(() => {
    const p = data?.message_pagination;
    return p ? Math.max(1, Math.ceil((p.total || 0) / (p.page_size || 20))) : 1;
  }, [data]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[9999] bg-black/20 backdrop-blur-sm flex items-start justify-center pt-8 md:pt-16 px-2 md:px-6" onClick={handleBackdropClick}>
      <div ref={panelRef} className="w-full md:max-w-3xl max-h-[80vh] md:max-h-[70vh] bg-white/90 backdrop-blur-lg border border-gray-200/60 dark:bg-gray-800/90 dark:border-gray-700 rounded-xl shadow-2xl ring-1 ring-black/5 flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Header search input */}
        <div className="px-4 py-3 border-b border-gray-200/60 dark:border-gray-700 bg-white/60 dark:bg-gray-800/60 backdrop-blur sticky top-0 z-10 flex items-center gap-2">
          <div className="relative flex-1">
            <Icon name="Search" size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
            <input
              ref={inputRef}
              value={query}
              onChange={handleChange}
              placeholder={t('search.placeholder', '搜索访客或消息')}
              className="w-full pl-9 pr-9 py-2.5 text-sm border border-gray-200/70 rounded-full bg-gray-50/80 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500/70 focus:border-blue-500"
            />
            {query && (
              <button className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300" onClick={handleClear} aria-label={t('common.clear', '清空')} title={t('common.clear', '清空')}>
                <Icon name="X" size={16} />
              </button>
            )}
          </div>
          <button className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700" onClick={onClose} aria-label={t('common.close', '关闭')} title={t('common.close', '关闭')}>
            <Icon name="X" size={18} />
          </button>
        </div>

        {/* Local highlight styles for sanitized HTML */}
        <style>{`
          .search-html mark {
            background-color: #FEF08A; /* Tailwind yellow-200 */
            color: #111827; /* Tailwind gray-900 */
            padding: 0 2px;
            border-radius: 4px;
            box-shadow: inset 0 0 0 1px rgba(0,0,0,0.04);
          }
          .dark .search-html mark {
            background-color: #854D0E; /* Tailwind yellow-900 */
            color: #FEF08A; /* Tailwind yellow-200 */
          }
        `}</style>

        {/* Tabs */}
        <div className="px-4 pt-2 border-b border-gray-100/80 dark:border-gray-700/80 bg-white/40 dark:bg-gray-800/40 backdrop-blur">
          <div className="flex items-center justify-between">
            <div className="inline-flex items-center gap-1 rounded-md bg-gray-100/60 dark:bg-gray-700/60 p-1 ring-1 ring-inset ring-gray-200/60 dark:ring-gray-600/60" role="tablist" aria-label={t('search.aria.tablist', '搜索分类')}>
              {tabs.map(tab => {
                const isActive = activeTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    role="tab"
                    aria-selected={isActive}
                    onClick={() => setActiveTab(tab.key)}
                    className={`inline-flex items-center px-2.5 py-1.5 text-sm rounded-md transition-all focus:outline-none ${isActive ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm ring-1 ring-gray-200/70 dark:ring-gray-500/70' : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-white/70 dark:hover:bg-gray-600/70'}`}
                  >
                    <Icon name={tab.icon} size={14} className={isActive ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500 dark:text-gray-400'} />
                    <span className="ml-1.5">{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto px-4 py-3 bg-white/30 dark:bg-gray-800/30">
          {!query ? (
            <div className="h-full flex items-center justify-center text-gray-400 dark:text-gray-500 text-sm">
              {t('search.emptyQueryHint', '输入关键词开始搜索')}
            </div>
          ) : (loading && !loadingMore) ? (
            <div className="h-full flex items-center justify-center text-gray-500 dark:text-gray-400 text-sm">
              <Icon name="Loader2" className="animate-spin mr-2" size={16} /> {t('search.searching', '正在搜索...')}
            </div>
          ) : error ? (
            <div className="h-full flex items-center justify-center text-red-500 dark:text-red-400 text-sm">
              <Icon name="AlertCircle" size={16} className="mr-2" /> {error}
            </div>
          ) : data ? (
            activeTab === 'all' ? (
              <div className="space-y-6">
                {/* Visitors section */}
                <div>
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">{t('search.sections.visitors', '访客')}（{data.visitor_count ?? data.visitors.length}）</div>
                  {data.visitors.length === 0 ? (
                    <div className="text-sm text-gray-400 dark:text-gray-500">{t('search.empty.visitors', '未找到相关访客')}</div>
                  ) : (
                    <div className="divide-y divide-gray-100 dark:divide-gray-700 bg-white dark:bg-gray-700 rounded-md border border-gray-100 dark:border-gray-600">
                      {data.visitors.slice(0, 10).map(v => (
                        <div key={v.id} className="p-1">{renderVisitorItem(v)}</div>
                      ))}
                    </div>
                  )}
                  {/* No pagination for visitors in 'all' tab as requested */}
                </div>

                {/* Messages section */}
                <div>
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">{t('search.sections.messages', '消息')}（{data.message_count ?? data.messages.length}）</div>
                  {data.messages.length === 0 ? (
                    <div className="text-sm text-gray-400 dark:text-gray-500">{t('search.empty.messages', '未找到相关消息')}</div>
                  ) : (
                    <div className="divide-y divide-gray-100 dark:divide-gray-700 bg-white dark:bg-gray-700 rounded-md border border-gray-100 dark:border-gray-600">
                      {data.messages.map(m => (
                        <div key={m.message_id_str} className="p-1">{renderMessageItem(m)}</div>
                      ))}
                    </div>
                  )}
                  {data.message_pagination && data.message_pagination.total > data.messages.length && (
                    <div className="mt-2">
                      <Pagination
                        currentPage={data.message_pagination.page}
                        totalPages={messageTotalPages}
                        onPageChange={(p) => setMessagePage(p)}
                      />
                    </div>
                  )}
                </div>
              </div>
            ) : activeTab === 'visitors' ? (
              <div>
                {accumulatedVisitors.length === 0 ? (
                  <div className="text-sm text-gray-400 dark:text-gray-500">{t('search.empty.visitors', '未找到相关访客')}</div>
                ) : (
                  <>
                    <div className="divide-y divide-gray-100 dark:divide-gray-700 bg-white dark:bg-gray-700 rounded-md border border-gray-100 dark:border-gray-600">
                      {accumulatedVisitors.map(v => (
                        <div key={v.id} className="p-1">{renderVisitorItem(v)}</div>
                      ))}
                    </div>
                    {/* Infinite scroll sentinel */}
                    <div ref={visitorSentinelRef} className="h-10 flex items-center justify-center mt-2">
                      {loadingMore && <Icon name="Loader2" className="animate-spin text-gray-400" size={20} />}
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div>
                {data.messages.length === 0 ? (
                  <div className="text-sm text-gray-400 dark:text-gray-500">{t('search.empty.messages', '未找到相关消息')}</div>
                ) : (
                  <div className="divide-y divide-gray-100 dark:divide-gray-700 bg-white dark:bg-gray-700 rounded-md border border-gray-100 dark:border-gray-600">
                    {data.messages.map(m => (
                      <div key={m.message_id_str} className="p-1">{renderMessageItem(m)}</div>
                    ))}
                  </div>
                )}
                {data.message_pagination && data.message_pagination.total > data.messages.length && (
                  <div className="mt-2">
                    <Pagination
                      currentPage={data.message_pagination.page}
                      totalPages={messageTotalPages}
                      onPageChange={(p) => setMessagePage(p)}
                    />
                  </div>
                )}
              </div>
            )
          ) : (
            <div className="h-full flex items-center justify-center text-gray-400 dark:text-gray-500 text-sm">{t('search.emptyQueryHint', '输入关键词开始搜索')}</div>
          )}
        </div>
        <div className="px-4 py-2 border-t border-gray-100 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400 bg-white/60 dark:bg-gray-800/60 backdrop-blur flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="hidden md:inline">{t('search.footer.tip', '小提示：')}</span>
            <span>{t('search.footer.escClose', 'Esc 关闭')}</span>
            <span>{t('search.footer.enterOpen', 'Enter 打开')}</span>
          </div>
          <div className="text-gray-400 dark:text-gray-500">{t('search.footer.summary', '搜索访客和消息')}</div>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default SearchPanel;

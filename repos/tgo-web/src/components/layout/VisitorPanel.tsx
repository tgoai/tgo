import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import i18n from '@/i18n';
import { User, AlertCircle, Loader2 } from 'lucide-react';
import TagManager from '../ui/TagManager';
import VisitorHeader from '../visitor/VisitorHeader';
import BasicInfoSection from '../visitor/BasicInfoSection';
import ImageCropModal from '../ui/ImageCropModal';

import AIInsightsSection from '../visitor/AIInsightsSection';
import SystemInfoSection from '../visitor/SystemInfoSection';
import RecentActivitySection from '../visitor/RecentActivitySection';
import { visitorApiService, type VisitorAttributesUpdateRequest } from '@/services/visitorApi';
import { tagsApiService } from '@/services/tagsApi';
import { useChannelStore } from '@/stores/channelStore';
import { useChatStore } from '@/stores/chatStore';
import { getChannelKey } from '@/utils/channelUtils';
import { useToast } from '@/hooks/useToast';
import type { Chat, ChannelVisitorExtra } from '@/types';
import { PlatformType } from '@/types';
import { toPlatformType } from '@/utils/platformUtils';
import { buildLastSeenText } from '@/utils/dateUtils';
import type { ExtendedVisitor, CustomAttribute, VisitorTag } from '@/data/mockVisitor';

interface VisitorPanelProps {
  activeChat?: Chat;
}

/**
 * 标准化 channel_type 字段，兼容字符串/数字
 */
const normalizeChannelType = (value: unknown): number | null => {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }

  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }

  return null;
};

interface VisitorContext {
  channelId: string | null;
  channelType: number | null;
}

/**
 * 从聊天信息中提取访客上下文
 */
const deriveVisitorContext = (chat?: Chat | null): VisitorContext => {
  if (!chat) {
    return {
      channelId: null,
      channelType: null
    };
  }

  const rawChannelType = chat.channelType;
  const channelType = normalizeChannelType(rawChannelType);
  const channelId = chat.channelId ?? chat.id ?? null;

  return {
    channelId,
    channelType
  };
};

/**
 * 将频道信息中的访客扩展数据转换为面板使用的扩展结构
 * 新接口 /v1/channels/info 的 extra 字段在访客渠道下为 ChannelVisitorExtra
 */
const toExtendedVisitorFromChannel = (extra: ChannelVisitorExtra): ExtendedVisitor => {
  const tags = Array.isArray(extra.tags)
    ? extra.tags.map((t, idx) => ({
        id: t.id || `tag_${idx}`,
        name: t.display_name || '',
        display_name: t.display_name || '',
        color: t.color || 'gray',
        weight: typeof t.weight === 'number' ? t.weight : 0
      }))
    : [];

  const customAttrsObj = (extra.custom_attributes || {}) as Record<string, unknown>;
  const customAttributes = Object.entries(customAttrsObj).map(([key, value], index) => ({
    id: `custom_${index}`,
    key,
    value: String(value ?? ''),
    editable: true,
  }));

  return {
    id: extra.id,
    name: extra.name || extra.nickname || i18n.t('chat.visitor.unknown', '未知访客'),
    avatar: extra.avatar_url || '',
    status: extra.is_online ? 'online' : 'offline',
    platform: extra.source || 'website',
    firstVisit: extra.first_visit_time || '',
    visitCount: 1,
    tags,
    basicInfo: {
      name: extra.name || '',
      email: extra.email || '',
      phone: extra.phone_number || '',
      nickname: extra.display_nickname || '',
      company: extra.company || '',
      jobTitle: extra.job_title || '',
      source: extra.source || '',
      note: extra.note || '',
      avatarUrl: extra.avatar_url || '',
      customAttributes,
    },
    aiInsights: {
      satisfaction: 4,
      emotion: { type: 'neutral', icon: 'Meh', label: i18n.t('chat.visitor.ai.emotion.neutral', '中性') },
    },
    systemInfo: {
      firstVisit: extra.first_visit_time || '',
      source: extra.source || i18n.t('chat.visitor.system.defaultSource', '官网客服'),
      browser: 'Chrome / macOS',
    },
    recentActivity: [],
    relatedTickets: [],
    aiPersonaTags: [],
  };
};

/**
 * Visitor information panel component with API integration and session switching support
 */
const VisitorPanel: React.FC<VisitorPanelProps> = ({ activeChat }) => {
  const [visitor, setVisitor] = useState<ExtendedVisitor | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hasLoadedInitial, setHasLoadedInitial] = useState(false);
  // Avatar crop modal state
  const [showCropModal, setShowCropModal] = useState(false);
  const [cropImageSrc, setCropImageSrc] = useState<string>('');
  const [cropImageMimeType, setCropImageMimeType] = useState<string>('image/png');
  const { t } = useTranslation();
  const { showToast } = useToast();
  const avatarInputRef = useRef<HTMLInputElement>(null);

  const { channelId, channelType } = useMemo(
    () => deriveVisitorContext(activeChat),
    [activeChat]
  );

  const compositeKey = useMemo(() => {
    if (!channelId || channelType == null) return null;
    return getChannelKey(channelId, channelType);
  }, [channelId, channelType]);

  const channelInfo = useChannelStore(state => (compositeKey ? state.channels[compositeKey] : undefined));
  const channelStoreError = useChannelStore(state => (compositeKey ? state.errors[compositeKey] : null));
  const isChannelFetching = useChannelStore(state => (compositeKey ? Boolean(state.inFlight[compositeKey]) : false));
  const ensureChannelInfo = useChannelStore(state => state.ensureChannel);

  // Derive recent activities from channel extra
  const recentActivities = useMemo(() => {
    const extra = channelInfo?.extra as ChannelVisitorExtra | undefined;
    const list = extra?.recent_activities;
    if (!Array.isArray(list)) return [] as NonNullable<ChannelVisitorExtra['recent_activities']>;
    // sort newest first (defensive)
    return [...list].sort((a, b) => new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime());
  }, [channelInfo]);
  // Derive system info from channel extra
  const systemInfo = useMemo(() => {
    const extra = channelInfo?.extra as ChannelVisitorExtra | undefined;
    return extra?.system_info || null;
  }, [channelInfo]);

  // Derive AI insights from channel extra
  const aiInsights = useMemo(() => {
    const extra = channelInfo?.extra as ChannelVisitorExtra | undefined;
    return extra?.ai_insights ?? null;
  }, [channelInfo]);


  useEffect(() => {
    if (!channelId) {
      setVisitor(null);
      setLoadError(null);
      setIsLoading(false);
      setHasLoadedInitial(false);
      return;
    }

    // Only auto-fetch when we have not fetched yet, nothing is in-flight, and no prior error exists
    if (!channelInfo && !isChannelFetching && !channelStoreError) {
      ensureChannelInfo({ channel_id: channelId, channel_type: channelType ?? 1 }).catch(error => {
        const message = error instanceof Error ? error.message : t('chat.visitor.load.failedDesc', '加载访客数据失败');
        setLoadError(message);
        showToast('error', t('chat.visitor.load.failedTitle', '加载访客信息失败'), message);
      });
    }
  }, [ensureChannelInfo, isChannelFetching, showToast, channelId, channelType, channelInfo, channelStoreError]);

  useEffect(() => {
    if (!channelId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(!hasLoadedInitial && isChannelFetching && !channelInfo);
  }, [isChannelFetching, channelId, channelInfo, hasLoadedInitial]);

  useEffect(() => {
    if (channelStoreError) {
      setLoadError(channelStoreError);
    } else {
      setLoadError(null);
    }
  }, [channelStoreError]);

  useEffect(() => {
    const extra = channelInfo?.extra as any;
    // 访客渠道：extra 应包含 visitor 字段集（例如 platform_open_id 等）
    const isVisitorExtra = extra && typeof extra === 'object' && 'platform_open_id' in extra && !('staff_id' in extra);
    if (isVisitorExtra) {
      setVisitor(toExtendedVisitorFromChannel(extra as ChannelVisitorExtra));
      setHasLoadedInitial(true);
    } else {
      // 非访客渠道（如员工），隐藏访客面板内容
      setVisitor(null);
    }
  }, [channelInfo]);

  // API集成的基本信息更新函数
  const handleUpdateBasicInfo = useCallback(async (
    field: 'name' | 'nickname' | 'email' | 'phone' | 'note',
    value: string
  ) => {
    if (!visitor) return;

    setIsUpdating(true);
    setUpdateError(null);

    try {
      // 准备API请求数据（同时携带当前自定义属性，确保同一请求体包含基础信息+自定义属性）
      const customAttributesForApi = (visitor.basicInfo.customAttributes || []).reduce((acc: Record<string, string | null>, attr: CustomAttribute) => {
        acc[attr.key] = attr.value;
        return acc;
      }, {} as Record<string, string | null>);

      const apiKey = field === 'phone' ? 'phone_number' : field; // 其余与API字段一致

      const updateData: VisitorAttributesUpdateRequest = {
        [apiKey]: value,
        custom_attributes: customAttributesForApi
      } as VisitorAttributesUpdateRequest;

      // 调用API更新访客属性
      await visitorApiService.updateVisitorAttributes(visitor.id, updateData);
      if (channelId) {
        await useChatStore.getState().syncChannelInfoAcrossUI(channelId, channelType ?? 1);
      }

      // 更新本地状态（字段名与本地basicInfo的映射）
      const localKey = field === 'phone' ? 'phone' : field; // 其余字段直接对应

      setVisitor((prev: ExtendedVisitor | null) => prev ? {
        ...prev,
        basicInfo: {
          ...prev.basicInfo,
          [localKey]: value
        }
      } : null);

      // 显示成功提示
      const labelMap: Record<string, string> = {
        name: t('chat.visitor.fields.name', '姓名'),
        nickname: t('chat.visitor.fields.nickname', '昵称'),
        email: t('chat.visitor.fields.email', '邮箱'),
        phone: t('chat.visitor.fields.phone', '电话'),
        note: t('chat.visitor.fields.note', '备注')
      };
      showToast('success', t('chat.visitor.update.successTitle', '更新成功'), t('chat.visitor.update.fieldUpdated', '{{field}}已更新', { field: labelMap[field] || t('chat.visitor.fields.field', '字段') }));

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('chat.visitor.update.failedDesc', '更新失败');
      setUpdateError(errorMessage);
      showToast('error', t('chat.visitor.update.failedTitle', '更新失败'), errorMessage);
      throw error; // 重新抛出错误，让EditableField处理
    } finally {
      setIsUpdating(false);
    }
  }, [visitor, showToast, channelId, channelType]);

  // API集成的自定义属性管理函数
  const handleAddCustomAttribute = useCallback(async (key: string, value: string) => {
    if (!visitor) return;

    setIsUpdating(true);
    setUpdateError(null);

    try {
      const newAttribute: CustomAttribute = {
        id: Date.now().toString(),
        key,
        value,
        editable: true
      };

      // 准备更新的自定义属性数据
      const currentAttributes = visitor.basicInfo.customAttributes || [];
      const updatedAttributes = [...currentAttributes, newAttribute];

      // 转换为API格式
      const customAttributesForApi = updatedAttributes.reduce((acc, attr) => {
        acc[attr.key] = attr.value;
        return acc;
      }, {} as Record<string, any>);

      // 调用API更新
      await visitorApiService.updateVisitorAttributes(visitor.id, {
        custom_attributes: customAttributesForApi
      });

      if (channelId) {
        await useChatStore.getState().syncChannelInfoAcrossUI(channelId, channelType ?? 1);
      }

      // 更新本地状态
      setVisitor((prev: ExtendedVisitor | null) => prev ? {
        ...prev,
        basicInfo: {
          ...prev.basicInfo,
          customAttributes: updatedAttributes
        }
      } : null);

      showToast('success', t('chat.visitor.customAttr.addSuccessTitle', '添加成功'), t('chat.visitor.customAttr.addSuccessDesc', '自定义属性已添加'));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('chat.visitor.customAttr.addFailedDesc', '添加失败');
      setUpdateError(errorMessage);
      showToast('error', t('chat.visitor.customAttr.addFailedTitle', '添加失败'), errorMessage);
    } finally {
      setIsUpdating(false);
    }
  }, [visitor, showToast, channelId, channelType]);

  const handleUpdateCustomAttribute = useCallback(async (id: string, key: string, value: string) => {
    if (!visitor) return;

    setIsUpdating(true);
    setUpdateError(null);

    try {
      // 更新本地属性数组
      const updatedAttributes = visitor.basicInfo.customAttributes?.map((attr: CustomAttribute) =>
        attr.id === id ? { ...attr, key, value } : attr
      ) || [];

      // 转换为API格式
      const customAttributesForApi = updatedAttributes.reduce((acc: Record<string, string | null>, attr: CustomAttribute) => {
        acc[attr.key] = attr.value;
        return acc;
      }, {} as Record<string, string | null>);

      // 调用API更新
      await visitorApiService.updateVisitorAttributes(visitor.id, {
        custom_attributes: customAttributesForApi
      });

      // 更新本地状态
      setVisitor(prev => prev ? {
        ...prev,
        basicInfo: {
          ...prev.basicInfo,
          customAttributes: updatedAttributes
        }
      } : null);

      showToast('success', t('chat.visitor.customAttr.updateSuccessTitle', '更新成功'), t('chat.visitor.customAttr.updateSuccessDesc', '自定义属性已更新'));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('chat.visitor.customAttr.updateFailedDesc', '更新失败');
      setUpdateError(errorMessage);
      showToast('error', t('chat.visitor.customAttr.updateFailedTitle', '更新失败'), errorMessage);
    } finally {
      setIsUpdating(false);
    }
  }, [visitor, showToast]);

  const handleDeleteCustomAttribute = useCallback(async (id: string) => {
    if (!visitor) return;

    setIsUpdating(true);
    setUpdateError(null);

    try {
      // 过滤掉要删除的属性
      const updatedAttributes = visitor.basicInfo.customAttributes?.filter(attr => attr.id !== id) || [];

      // 转换为API格式
      const customAttributesForApi = updatedAttributes.reduce((acc, attr) => {
        acc[attr.key] = attr.value;
        return acc;
      }, {} as Record<string, any>);

      // 调用API更新
      await visitorApiService.updateVisitorAttributes(visitor.id, {
        custom_attributes: customAttributesForApi
      });

      // 更新本地状态
      setVisitor(prev => prev ? {
        ...prev,
        basicInfo: {
          ...prev.basicInfo,
          customAttributes: updatedAttributes
        }
      } : null);

      showToast('success', t('chat.visitor.customAttr.deleteSuccessTitle', '删除成功'), t('chat.visitor.customAttr.deleteSuccessDesc', '自定义属性已删除'));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('chat.visitor.customAttr.deleteFailedDesc', '删除失败');
      setUpdateError(errorMessage);
      showToast('error', t('chat.visitor.customAttr.deleteFailedTitle', '删除失败'), errorMessage);
    } finally {
      setIsUpdating(false);
    }
  }, [visitor, showToast]);
  // 获取常用标签（点击“+ 添加”时触发）
  const fetchCommonTags = useCallback(async () => {
    const res = await tagsApiService.listVisitorTags({ limit: 50 });
    return res.data.map(tag => ({
      id: tag.id,
      display_name: tag.display_name,
      name: tag.name,
      color: tag.color || 'gray',
      weight: tag.weight
    }));
  }, []);

  // 选择已有标签：仅建立关联
  const handleAssociateExistingTag = useCallback(async (tagId: string) => {
    if (!visitor) return;

    setIsUpdating(true);
    setUpdateError(null);
    try {
      await tagsApiService.createVisitorTag({ visitor_id: visitor.id, tag_id: tagId });
      if (channelId) {
        await useChatStore.getState().syncChannelInfoAcrossUI(channelId, channelType ?? 1);
      }
      showToast('success', t('chat.visitor.tags.addSuccessTitle', '添加成功'), t('chat.visitor.tags.addSuccessDesc', '标签已添加'));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('chat.visitor.tags.addFailedDesc', '添加标签失败');
      setUpdateError(errorMessage);
      showToast('error', t('chat.visitor.tags.addFailedTitle', '添加失败'), errorMessage);
      console.error('关联已有标签失败:', error);
    } finally {
      setIsUpdating(false);
    }
  }, [visitor, showToast, channelId, channelType]);


  // API集成的标签管理函数
  // 自定义输入：先创建标签，再建立关联
  const handleAddTag = useCallback(async (tagData: Omit<VisitorTag, 'id'>) => {
    if (!visitor) return;

    setIsUpdating(true);
    setUpdateError(null);

    try {
      // Step 1: Create new tag
      let tagId: string | null = null;
      try {
        const newTagResponse = await tagsApiService.createTag({
          name: tagData.name,
          category: 'visitor',
          weight: tagData.weight || 0,
          color: tagData.color || null,
          description: null
        });
        tagId = newTagResponse.id;
      } catch (createErr: any) {
        // 如果后端限制重复创建并返回冲突错误，回退到查询已存在标签
        try {
          const existing = await tagsApiService.listVisitorTags({ search: tagData.name, limit: 1 });
          const found = existing.data.find(t => t.name.toLowerCase() === tagData.name.toLowerCase());
          if (found) {
            tagId = found.id;
          } else {
            throw createErr;
          }
        } catch (e) {
          throw createErr;
        }
      }

      if (!tagId) throw new Error(t('chat.visitor.tags.errors.noTagId', '无法获取标签ID'));

      // Step 2: Create visitor-tag association
      await tagsApiService.createVisitorTag({
        visitor_id: visitor.id,
        tag_id: tagId
      });

      // Step 3: Sync across UI
      if (channelId) {
        await useChatStore.getState().syncChannelInfoAcrossUI(channelId, channelType ?? 1);
      }

      showToast('success', t('chat.visitor.tags.addSuccessTitle', '添加成功'), t('chat.visitor.tags.addSuccessDesc', '标签已添加'));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('chat.visitor.tags.addFailedDesc', '添加标签失败');
      setUpdateError(errorMessage);
      showToast('error', t('chat.visitor.tags.addFailedTitle', '添加失败'), errorMessage);
      console.error('添加标签失败:', error);
    } finally {
      setIsUpdating(false);
    }
  }, [visitor, showToast, channelId, channelType]);

  const handleUpdateTag = useCallback(async (id: string, updates: Partial<VisitorTag>) => {
    if (!visitor) return;

    setIsUpdating(true);
    setUpdateError(null);

    try {
      // Find the tag to update
      const tagToUpdate = visitor.tags.find(tag => tag.id === id);
      if (!tagToUpdate) {
        throw new Error(t('chat.visitor.tags.errors.notFound', '标签不存在'));
      }

      // Update the tag via API (only weight and color can be updated)
      const updateData: { weight?: number; color?: string } = {};
      if (updates.weight !== undefined) {
        updateData.weight = updates.weight;
      }
      if (updates.color !== undefined) {
        updateData.color = updates.color;
      }

      if (Object.keys(updateData).length > 0) {
        await tagsApiService.updateTag(tagToUpdate.id, updateData);
      }

      // Refresh visitor data to get updated tags
      if (channelId) {
        await useChatStore.getState().syncChannelInfoAcrossUI(channelId, channelType ?? 1);
      }

      showToast('success', t('chat.visitor.tags.updateSuccessTitle', '更新成功'), t('chat.visitor.tags.updateSuccessDesc', '标签已更新'));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('chat.visitor.tags.updateFailedDesc', '更新标签失败');
      setUpdateError(errorMessage);
      showToast('error', t('chat.visitor.tags.updateFailedTitle', '更新失败'), errorMessage);
      console.error('更新标签失败:', error);
    } finally {
      setIsUpdating(false);
    }
  }, [visitor, showToast, channelId, channelType]);

  const handleRemoveTag = useCallback(async (id: string) => {
    if (!visitor) return;

    setIsUpdating(true);
    setUpdateError(null);

    try {
      // 使用按 visitor_id + tag_id 删除关联的接口
      await tagsApiService.deleteVisitorTagByVisitorAndTag(visitor.id, id);
      if (channelId) {
        await useChatStore.getState().syncChannelInfoAcrossUI(channelId, channelType ?? 1);
      }
      showToast('success', t('chat.visitor.tags.removeSuccessTitle', '删除成功'), t('chat.visitor.tags.removeSuccessDesc', '标签已删除'));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('chat.visitor.tags.removeFailedDesc', '删除标签失败');
      setUpdateError(errorMessage);
      showToast('error', t('chat.visitor.tags.removeFailedTitle', '删除失败'), errorMessage);
      console.error('删除标签失败:', error);
    } finally {
      setIsUpdating(false);
    }
  }, [visitor, showToast, channelId, channelType]);

  // 头像上传处理
  const handleAvatarClick = useCallback(() => {
    avatarInputRef.current?.click();
  }, []);

  const handleAvatarChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !visitor) return;

    // 验证文件类型
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      showToast('error', t('chat.visitor.avatar.invalidTypeTitle', '文件类型错误'), t('chat.visitor.avatar.invalidTypeDesc', '请选择 JPEG、PNG、GIF 或 WebP 格式的图片'));
      return;
    }

    // 验证文件大小 (5MB)
    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
      showToast('error', t('chat.visitor.avatar.fileTooLargeTitle', '文件过大'), t('chat.visitor.avatar.fileTooLargeDesc', '图片大小不能超过 5MB'));
      return;
    }

    // 创建 object URL 用于裁剪预览
    const imageUrl = URL.createObjectURL(file);
    setCropImageSrc(imageUrl);
    setCropImageMimeType(file.type);
    setShowCropModal(true);

    // 清空 input 以便可以重新选择同一个文件
    if (avatarInputRef.current) {
      avatarInputRef.current.value = '';
    }
  }, [visitor, showToast, t]);

  // 取消裁剪
  const handleCropCancel = useCallback(() => {
    setShowCropModal(false);
    // 释放 object URL
    if (cropImageSrc) {
      URL.revokeObjectURL(cropImageSrc);
    }
    setCropImageSrc('');
  }, [cropImageSrc]);

  // 确认裁剪并上传
  const handleCropConfirm = useCallback(async (blob: Blob) => {
    if (!visitor) return;

    setShowCropModal(false);
    // 释放 object URL
    if (cropImageSrc) {
      URL.revokeObjectURL(cropImageSrc);
    }
    setCropImageSrc('');

    setIsUploadingAvatar(true);
    setUpdateError(null);

    try {
      // 将 Blob 转换为 File 对象
      const fileName = `avatar_${Date.now()}.${cropImageMimeType.split('/')[1] || 'png'}`;
      const file = new File([blob], fileName, { type: cropImageMimeType });

      const response = await visitorApiService.uploadAvatar(visitor.id, file);
      
      // 更新本地状态，添加时间戳参数避免浏览器缓存
      const avatarUrlWithCacheBust = `${response.avatar_url}?t=${Date.now()}`;
      setVisitor((prev: ExtendedVisitor | null) => prev ? {
        ...prev,
        avatar: avatarUrlWithCacheBust,
        basicInfo: {
          ...prev.basicInfo,
          avatarUrl: avatarUrlWithCacheBust
        }
      } : null);

      // 同步更新到其他UI
      if (channelId) {
        const syncedInfo = await useChatStore.getState().syncChannelInfoAcrossUI(channelId, channelType ?? 1);
        // 如果同步返回的头像 URL 没有缓存参数，手动添加以强制刷新聊天列表中的头像
        if (syncedInfo && syncedInfo.avatar) {
          const avatarWithCacheBust = syncedInfo.avatar.includes('?') 
            ? `${syncedInfo.avatar}&t=${Date.now()}` 
            : `${syncedInfo.avatar}?t=${Date.now()}`;
          // 更新 channelStore 中的缓存
          useChannelStore.getState().updateChannelAvatar(channelId, channelType ?? 1, avatarWithCacheBust);
          // 重新应用到 chatStore
          useChatStore.getState().applyChannelInfo(channelId, channelType ?? 1, {
            ...syncedInfo,
            avatar: avatarWithCacheBust
          });
        }
      }

      showToast('success', t('chat.visitor.avatar.uploadSuccessTitle', '上传成功'), t('chat.visitor.avatar.uploadSuccessDesc', '访客头像已更新'));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('chat.visitor.avatar.uploadFailedDesc', '上传失败');
      setUpdateError(errorMessage);
      showToast('error', t('chat.visitor.avatar.uploadFailedTitle', '上传失败'), errorMessage);
      console.error('上传访客头像失败:', error);
    } finally {
      setIsUploadingAvatar(false);
    }
  }, [visitor, channelId, channelType, cropImageSrc, cropImageMimeType, showToast, t]);

  // 渲染空状态或错误状态
  if (!visitor) {
    return (
      <aside className="w-72 bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg border-l border-gray-200/60 dark:border-gray-700/60 flex items-center justify-center shrink-0 font-sans antialiased">
        <div className="text-center text-gray-500 dark:text-gray-400 px-4">
          {isLoading ? (
            <>
              <Loader2 size={48} className="mx-auto mb-4 text-gray-300 dark:text-gray-600 animate-spin" />
              <p className="text-sm leading-5">{t('chat.visitor.ui.loading', '正在加载访客信息...')}</p>
            </>
          ) : loadError ? (
            <>
              <AlertCircle size={48} className="mx-auto mb-4 text-red-300 dark:text-red-500" />
              <p className="text-sm leading-5 text-red-600 dark:text-red-400 mb-2">{t('chat.visitor.ui.loadFailed', '加载失败')}</p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mb-4">{loadError}</p>
              <button
                onClick={() => window.location.reload()}
                className="px-3 py-1 text-xs bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md transition-colors"
              >
                {t('common.retry', '重试')}
              </button>
            </>
          ) : !activeChat ? (
            <>
              <User size={48} className="mx-auto mb-4 text-gray-300 dark:text-gray-600" />
              <p className="text-sm leading-5">{t('chat.visitor.ui.selectConversation', '选择聊天查看访客信息')}</p>
            </>
          ) : (
            <>
              <User size={48} className="mx-auto mb-4 text-gray-300 dark:text-gray-600" />
              <p className="text-sm leading-5">{t('chat.visitor.ui.noInfo', '暂无访客信息')}</p>
            </>
          )}
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-72 bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg border-l border-gray-200/60 dark:border-gray-700/60 flex flex-col shrink-0 font-sans antialiased">
      {/* Panel Header */}
      <div className="p-4 border-b border-gray-200/60 dark:border-gray-700/60 sticky top-0 bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg z-10">
        {/* Hidden file input for avatar upload */}
        <input
          ref={avatarInputRef}
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          className="hidden"
          onChange={handleAvatarChange}
        />
        {/* Visitor Avatar and Name */}
        <VisitorHeader
          name={(() => {
            const extra = channelInfo?.extra as ChannelVisitorExtra | undefined;
            return extra?.display_nickname || visitor.name;
          })()}
          status={visitor.status || 'offline'}
          avatar={visitor.avatar}
          platformType={(() => {
            const extra: any = channelInfo?.extra;
            const fromExtra: PlatformType | undefined = (extra && typeof extra === 'object' && 'platform_type' in extra)
              ? (extra.platform_type as PlatformType)
              : undefined;
            const fallbackPlatform = activeChat?.platform || visitor.platform || '';
            return fromExtra ?? toPlatformType(fallbackPlatform);
          })()}
          lastSeenText={(() => {
            const extra = channelInfo?.extra as ChannelVisitorExtra | undefined;
            return buildLastSeenText(extra?.last_offline_time, extra?.is_online ?? null) || undefined;
          })()}
          onAvatarClick={handleAvatarClick}
          isUploading={isUploadingAvatar}
          visitorId={channelId || visitor.id}
        />

      </div>

      {/* Panel Content */}
      <div className="relative flex-grow overflow-y-auto p-4 space-y-6" style={{ height: 0 }}>
        {/* Loading/Error State (absolute overlay to avoid layout shift) */}
        {isUpdating && (
          <div className="pointer-events-none absolute top-2 left-1/2 -translate-x-1/2 z-20 flex items-center text-xs text-blue-700 dark:text-blue-400 bg-white/80 dark:bg-gray-800/80 backdrop-blur px-2 py-1 rounded border border-blue-100 dark:border-blue-800 shadow-sm">
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            {t('common.updating', '更新中...')}
          </div>
        )}

        {(updateError || loadError) && (
          <div className="flex items-center py-2 px-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800/50 rounded-md">
            <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
            <span className="flex-1">{updateError || loadError}</span>
          </div>
        )}

        {/* Basic Info */}
        <BasicInfoSection
          basicInfo={visitor.basicInfo}
          onUpdateBasicInfo={handleUpdateBasicInfo}
          onAddCustomAttribute={handleAddCustomAttribute}
          onUpdateCustomAttribute={handleUpdateCustomAttribute}
          onDeleteCustomAttribute={handleDeleteCustomAttribute}
        />



        {/* AI 洞察（仅在存在有效字段时显示）*/}
        <AIInsightsSection
          satisfactionScore={aiInsights?.satisfaction_score ?? null}
          emotionScore={aiInsights?.emotion_score ?? null}
          intent={aiInsights?.intent ?? null}
          insightSummary={aiInsights?.insight_summary ?? null}
        />

        {/* Tags */}
        <div className="pt-4 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">{t('chat.visitor.tags.title', '标签')}</h4>
            {isUpdating && (
              <div className="flex items-center text-xs text-blue-600 dark:text-blue-400">
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                {t('common.updating', '更新中')}
              </div>
            )}
          </div>
          <TagManager
            tags={visitor.tags}
            onAddTag={handleAddTag}
            onUpdateTag={handleUpdateTag}
            onRemoveTag={handleRemoveTag}
            fetchCommonTags={fetchCommonTags}
            onAssociateExistingTag={handleAssociateExistingTag}
            maxTags={8}
            className="mt-1"
          />
        </div>

        {/* System Info Section */}
        <SystemInfoSection
          systemInfo={systemInfo}
          language={(channelInfo?.extra as ChannelVisitorExtra | undefined)?.language}
          timezone={(channelInfo?.extra as ChannelVisitorExtra | undefined)?.timezone}
          ipAddress={(channelInfo?.extra as ChannelVisitorExtra | undefined)?.ip_address}
          displayLocation={(channelInfo?.extra as ChannelVisitorExtra | undefined)?.display_location}
        />

        {/* Recent Activity Section */}
        <RecentActivitySection activities={recentActivities} />

      </div>

      {/* Avatar Crop Modal */}
      <ImageCropModal
        isOpen={showCropModal}
        imageSrc={cropImageSrc}
        aspect={1}
        mimeType={cropImageMimeType}
        title={t('chat.visitor.avatar.cropTitle', '裁剪头像')}
        onCancel={handleCropCancel}
        onConfirm={handleCropConfirm}
      />
    </aside>
  );
};

export default VisitorPanel;

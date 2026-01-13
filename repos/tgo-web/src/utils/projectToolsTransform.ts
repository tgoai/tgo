/**
 * Project Tools Data Transformation Utilities
 * Transforms API data to component-compatible formats
 * Updated to use NEW /v1/ai/tools API (AiToolResponse)
 */

import type { AiToolResponse, AiTool, ToolCategory, AiToolStatus, ToolStatus, ToolSourceType } from '@/types';
import { TransformUtils } from './base/BaseTransform';

/**
 * Transform API ToolStatus to component AiToolStatus
 */
export const transformToolStatus = (apiStatus: ToolStatus): AiToolStatus =>
  TransformUtils.transformToolStatus(apiStatus);

/**
 * Transform API category to component ToolCategory
 */
export const transformCategory = (apiCategory: string | null): ToolCategory =>
  TransformUtils.transformCategory(apiCategory);

/**
 * Transform ToolSourceType to readable string
 */
export const transformSourceType = (sourceType: ToolSourceType): string =>
  TransformUtils.transformSourceType(sourceType);

/**
 * Generate mock data for fields not provided by API
 */
export const generateMockAiToolData = (aiTool: AiToolResponse) => {
  // Generate consistent mock data based on tool ID
  const seed = aiTool.id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);

  // Generate rating (3.5 - 5.0)
  const rating = 3.5 + (seed % 15) / 10;

  // Generate usage count (100 - 5000)
  const usageCount = 100 + (seed % 4900);

  // Generate success rate (85% - 99%)
  const successRate = 85 + (seed % 15);

  // Generate response time (50ms - 2000ms)
  const responseTime = 50 + (seed % 1950);
  const avgResponseTime = responseTime < 1000 ? `${responseTime}ms` : `${(responseTime / 1000).toFixed(1)}s`;


  return {
    rating: Math.round(rating * 10) / 10,
    usageCount,
    successRate,
    avgResponseTime,
    author: "",
  };
};

/**
 * Transform API AiToolResponse to component AiTool
 * Uses NEW /v1/ai/tools API response format
 */
export const transformAiToolResponse = (aiTool: AiToolResponse): AiTool => {
  const mockData = generateMockAiToolData(aiTool);

  // Determine tool status based on deleted_at field
  // deleted_at !== null means the tool is soft-deleted (inactive)
  // deleted_at === null means the tool is active
  const isActive = !aiTool.deleted_at;
  const toolStatus: ToolStatus = isActive ? 'ACTIVE' : 'INACTIVE';

  // Extract category from tool name or config if available
  // For now, default to 'integration' since new API doesn't have category field
  let category: ToolCategory = 'integration';
  let author: string = mockData.author;

  if (aiTool.transport_type === 'plugin') {
    category = 'integration'; // Or a dedicated category if added to ToolCategory type
    author = '插件';
  } else if (aiTool.transport_type === 'http_webhook') {
    category = 'integration';
    author = 'HTTP 工具';
  }

  return {
    id: aiTool.id,
    name: aiTool.name || '未知工具',
    title: aiTool.title || undefined,
    title_zh: aiTool.title_zh || undefined,
    title_en: aiTool.title_en || undefined,
    description: aiTool.description || '暂无描述',
    category: category,
    status: isActive ? 'active' : 'inactive', // Use deleted_at to determine status
    version: 'v1.0.0', // New API doesn't have version field
    author: author,
    lastUpdated: new Date(aiTool.updated_at).toLocaleDateString('zh-CN'),
    usageCount: mockData.usageCount,
    rating: mockData.rating,
    tags: [], // New API doesn't have tags
    capabilities: [], // Will be populated from config if available
    successRate: mockData.successRate,
    avgResponseTime: mockData.avgResponseTime,
    input_schema: aiTool.config?.input_schema || aiTool.config || {},
    short_no: undefined, // New API doesn't have short_no
    config: {
      project_id: aiTool.project_id,
      tool_id: aiTool.id, // In new API, tool_id is the same as id
      is_enabled: isActive, // Map deleted_at to is_enabled for backward compatibility
      installed_at: aiTool.created_at, // Use created_at as installed_at
      tool_status: toolStatus,
      execution_count: 0, // Not available in new API
      // Store additional new API fields
      tool_type: aiTool.tool_type,
      transport_type: aiTool.transport_type,
      endpoint: aiTool.endpoint,
      deleted_at: aiTool.deleted_at,
    },
  };
};

/**
 * Transform array of API AiToolResponse to component AiTool array
 */
export const transformAiToolResponseList = (aiTools: AiToolResponse[]): AiTool[] => {
  return aiTools.map(transformAiToolResponse);
};

/**
 * Get display title for a tool based on current language
 */
export const getToolDisplayTitle = (tool: AiTool, language: string): string => {
  if (language.startsWith('zh')) {
    return tool.title_zh || tool.title || tool.name;
  }
  return tool.title_en || tool.title || tool.name;
};

/**
 * Filter project tools by enabled status (for client-side filtering)
 */
export const filterProjectToolsByEnabled = (tools: AiTool[], enabledFilter: 'all' | 'enabled' | 'disabled'): AiTool[] => {
  if (enabledFilter === 'all') return tools;
  
  return tools.filter(tool => {
    const isEnabled = tool.status === 'active';
    return enabledFilter === 'enabled' ? isEnabled : !isEnabled;
  });
};

/**
 * Filter project tools by category (for client-side filtering)
 */
export const filterProjectToolsByCategory = (tools: AiTool[], category: ToolCategory): AiTool[] => {
  if (category === 'all') return tools;
  return tools.filter(tool => tool.category === category);
};

/**
 * Search project tools by name, description, or tags (for client-side search)
 */
export const searchProjectTools = (tools: AiTool[], query: string): AiTool[] => {
  if (!query.trim()) return tools;
  
  const lowerQuery = query.toLowerCase();
  return tools.filter(tool => 
    tool.name.toLowerCase().includes(lowerQuery) ||
    tool.description.toLowerCase().includes(lowerQuery) ||
    tool.tags.some(tag => tag.toLowerCase().includes(lowerQuery)) ||
    tool.author.toLowerCase().includes(lowerQuery)
  );
};

/**
 * Sort project tools by different criteria
 */
export const sortProjectTools = (tools: AiTool[], sortBy: 'name' | 'recent' | 'rating' | 'usage'): AiTool[] => {
  const sortedTools = [...tools];
  
  switch (sortBy) {
    case 'name':
      return sortedTools.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'));
    case 'recent':
      return sortedTools.sort((a, b) => 
        new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime()
      );
    case 'rating':
      return sortedTools.sort((a, b) => b.rating - a.rating);
    case 'usage':
      return sortedTools.sort((a, b) => b.usageCount - a.usageCount);
    default:
      return sortedTools;
  }
};

/**
 * Get enabled status display name in Chinese
 */
export const getEnabledStatusDisplayName = (enabledFilter: 'all' | 'enabled' | 'disabled'): string => {
  const statusNames: Record<'all' | 'enabled' | 'disabled', string> = {
    'all': '全部',
    'enabled': '已启用',
    'disabled': '已禁用',
  };
  
  return statusNames[enabledFilter] || '全部';
};

/**
 * Get enabled status color class for UI
 */
export const getEnabledStatusColorClass = (isEnabled: boolean): string => {
  return isEnabled 
    ? 'text-green-600 bg-green-100' 
    : 'text-gray-600 bg-gray-100';
};

/**
 * Get category display name in Chinese
 */
export const getCategoryDisplayName = (category: ToolCategory): string => {
  const categoryNames: Record<ToolCategory, string> = {
    'all': '全部',
    'productivity': '效率工具',
    'communication': '通信工具',
    'data': '数据分析',
    'ai': 'AI工具',
    'integration': '集成服务',
  };
  
  return categoryNames[category] || '未知分类';
};

/**
 * Check if a project tool can be deleted
 * @deprecated - Toggle functionality removed in new API, use delete instead
 */
export const canToggleProjectTool = (tool: AiTool): boolean => {
  // Can delete if it's not already deleted
  return tool.status !== 'inactive';
};

/**
 * Check if a project tool can be deleted (soft delete)
 */
export const canDeleteProjectTool = (tool: AiTool): boolean => {
  // Can delete if it's not already deleted
  return tool.status !== 'inactive';
};

/**
 * Get project tool action button text
 */
export const getProjectToolActionText = (_tool: AiTool, action: 'delete' | 'uninstall'): string => {
  switch (action) {
    case 'delete':
    case 'uninstall':
      return '删除';
    default:
      return '操作';
  }
};

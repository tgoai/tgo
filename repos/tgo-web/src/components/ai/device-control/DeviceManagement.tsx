/**
 * DeviceManagement Component
 * Main page for managing connected devices
 */

import React, { useState, useEffect, useMemo, useContext } from 'react';
import { useTranslation } from 'react-i18next';

import {
  MonitorSmartphone,
  Plus,
  Search,
  RefreshCw,
  Wifi,
  WifiOff,
  AlertCircle,
  Activity,
  X,
  Settings,
  Cpu,
  ChevronDown,
  ChevronUp,
  Loader2,
} from 'lucide-react';
import DeviceCard from './DeviceCard';
import BindCodeModal from './BindCodeModal';
import EditDeviceModal from './EditDeviceModal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import { ComputerUseSessionMonitor } from '../remote-agent';
import { ToastContext } from '@/components/ui/ToastContainer';
import { useDeviceControlStore } from '@/stores/deviceControlStore';
import { useAuthStore } from '@/stores/authStore';
import AIProvidersApiService from '@/services/aiProvidersApi';
import ProjectConfigApiService from '@/services/projectConfigApi';
import type { Device, DeviceStatus } from '@/types/deviceControl';

const DeviceManagement: React.FC = () => {
  const { t } = useTranslation();
  const toast = useContext(ToastContext);
  const projectId = useAuthStore(s => s.user?.project_id);

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<DeviceStatus | 'all'>('all');
  const [showBindCodeModal, setShowBindCodeModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deviceToDelete, setDeviceToDelete] = useState<Device | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState(false);
  const [deviceToDisconnect, setDeviceToDisconnect] = useState<Device | null>(null);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  
  // Session monitor state
  const [showSessionMonitor, setShowSessionMonitor] = useState(false);
  const [monitoringSessionId, setMonitoringSessionId] = useState<string | null>(null);

  // Global model settings state
  const [showModelSettings, setShowModelSettings] = useState(false);
  const [modelOptions, setModelOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [modelLoading, setModelLoading] = useState(false);
  const [globalModelSelection, setGlobalModelSelection] = useState('');
  const [isSavingModel, setIsSavingModel] = useState(false);

  const {
    devices,
    isLoading,
    error,
    loadDevices,
    deleteDevice,
    disconnectDevice,
    clearError,
  } = useDeviceControlStore();

  // Load model options and current config
  useEffect(() => {
    if (!projectId) return;

    const loadModelConfig = async () => {
      setModelLoading(true);
      try {
        // Load available chat models
        const aiProvidersSvc = new AIProvidersApiService();
        const modelsRes = await aiProvidersSvc.listProjectModels({
          model_type: 'chat',
          is_active: true,
        });
        const options = (modelsRes.data || []).map((m: { provider_id: string; model_id: string; model_name: string; provider_name: string }) => ({
          value: `${m.provider_id}:${m.model_id}`,
          label: `${m.model_name} · ${m.provider_name}`,
        }));
        setModelOptions(options);

        // Load current config
        const configSvc = new ProjectConfigApiService();
        const config = await configSvc.getAIConfig(projectId);
        if (config.device_control_provider_id && config.device_control_model) {
          setGlobalModelSelection(`${config.device_control_provider_id}:${config.device_control_model}`);
        }
      } catch (err) {
        console.error('Failed to load model config:', err);
      } finally {
        setModelLoading(false);
      }
    };

    loadModelConfig();
  }, [projectId]);

  // Save global model selection
  const handleSaveGlobalModel = async () => {
    if (!projectId) return;

    setIsSavingModel(true);
    try {
      const configSvc = new ProjectConfigApiService();
      
      let providerId: string | null = null;
      let model: string | null = null;
      
      if (globalModelSelection) {
        const parts = globalModelSelection.split(':');
        providerId = parts[0];
        model = parts.slice(1).join(':');
      }

      await configSvc.upsertAIConfig(projectId, {
        device_control_provider_id: providerId,
        device_control_model: model,
      });

      toast?.showToast('success', t('common.saveSuccess', '保存成功'));
    } catch (err) {
      const message = err instanceof Error ? err.message : t('common.saveFailed', '保存失败');
      toast?.showToast('error', message);
    } finally {
      setIsSavingModel(false);
    }
  };

  // Load devices on mount
  useEffect(() => {
    loadDevices();
  }, [loadDevices]);

  // Filter devices
  const filteredDevices = useMemo(() => {
    let filtered = devices;

    // Filter by status
    if (statusFilter !== 'all') {
      filtered = filtered.filter((d) => d.status === statusFilter);
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (d) =>
          d.device_name.toLowerCase().includes(query) ||
          d.os.toLowerCase().includes(query)
      );
    }

    return filtered;
  }, [devices, statusFilter, searchQuery]);

  // Stats
  const onlineCount = devices.filter((d) => d.status === 'online').length;
  const offlineCount = devices.filter((d) => d.status === 'offline').length;

  // Handlers
  const handleEdit = (device: Device) => {
    setSelectedDevice(device);
    setShowEditModal(true);
  };

  const handleDelete = (device: Device) => {
    setDeviceToDelete(device);
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deviceToDelete) return;
    setIsDeleting(true);
    try {
      await deleteDevice(deviceToDelete.id);
      setShowDeleteConfirm(false);
      setDeviceToDelete(null);
    } catch (err) {
      console.error('Failed to delete device:', err);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDisconnect = (device: Device) => {
    setDeviceToDisconnect(device);
    setShowDisconnectConfirm(true);
  };

  const handleDisconnectConfirm = async () => {
    if (!deviceToDisconnect) return;
    setIsDisconnecting(true);
    try {
      await disconnectDevice(deviceToDisconnect.id);
      setShowDisconnectConfirm(false);
      setDeviceToDisconnect(null);
    } catch (err) {
      console.error('Failed to disconnect device:', err);
    } finally {
      setIsDisconnecting(false);
    }
  };

  const handleRefresh = () => {
    clearError();
    loadDevices();
  };

  return (
    <main className="flex-grow flex flex-col bg-[#f8fafc] dark:bg-gray-950 overflow-hidden">
      {/* Header */}
      <header className="px-8 py-5 bg-white/80 dark:bg-gray-900/80 backdrop-blur-xl border-b border-gray-200/50 dark:border-gray-800/50 flex flex-col md:flex-row md:items-center justify-between gap-4 sticky top-0 z-30">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <MonitorSmartphone className="w-7 h-7 text-blue-600" />
            {t('deviceControl.title', '设备控制')}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {t('deviceControl.subtitle', '管理 AI 员工可控制的远程设备')}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="relative group hidden sm:block">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
            <input
              type="text"
              placeholder={t('deviceControl.search.placeholder', '搜索设备...')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-2 w-48 lg:w-64 bg-gray-100/50 dark:bg-gray-800/50 border-transparent focus:bg-white dark:focus:bg-gray-800 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 rounded-xl text-sm transition-all outline-none"
            />
          </div>

          {/* Refresh */}
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl transition-colors"
            title={t('common.refresh', '刷新')}
          >
            <RefreshCw
              className={`w-5 h-5 text-gray-500 ${isLoading ? 'animate-spin' : ''}`}
            />
          </button>

          {/* Session Monitor */}
          <button
            onClick={() => setShowSessionMonitor(true)}
            className="flex items-center gap-2 px-3 py-2 hover:bg-purple-50 dark:hover:bg-purple-900/20 rounded-xl transition-colors group"
            title={t('deviceControl.sessionMonitor.title', '会话监控')}
          >
            <Activity className="w-5 h-5 text-purple-500 group-hover:text-purple-600" />
            <span className="hidden lg:inline text-sm font-medium text-gray-600 dark:text-gray-300 group-hover:text-purple-600 dark:group-hover:text-purple-400">
              {t('deviceControl.sessionMonitor.title', '会话监控')}
            </span>
          </button>

          <div className="h-8 w-px bg-gray-200 dark:bg-gray-800 mx-1 hidden sm:block" />

          {/* Add Device */}
          <button
            onClick={() => setShowBindCodeModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl shadow-lg shadow-blue-200 dark:shadow-none transition-all active:scale-95"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden lg:inline">
              {t('deviceControl.addDevice', '添加设备')}
            </span>
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-[1600px] mx-auto p-8 space-y-8">
          {/* Banner */}
          <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-3xl p-6 text-white shadow-xl shadow-blue-200 dark:shadow-none flex flex-col md:flex-row items-center justify-between gap-6 relative overflow-hidden">
            <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10" />
            <div className="relative z-10">
              <h3 className="text-xl font-bold flex items-center gap-2">
                <MonitorSmartphone className="w-6 h-6" />
                {t('deviceControl.banner.title', '远程设备控制')}
              </h3>
              <p className="text-blue-100 text-sm mt-1 opacity-90 max-w-xl">
                {t(
                  'deviceControl.banner.description',
                  '连接您的电脑或移动设备，让 AI 员工能够直接操控屏幕，完成更复杂的自动化任务。'
                )}
              </p>
            </div>
          </div>

          {/* Global Model Settings */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <button
              onClick={() => setShowModelSettings(!showModelSettings)}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-xl">
                  <Settings className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                </div>
                <div className="text-left">
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                    {t('deviceControl.settings.title', '设备控制设置')}
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t('deviceControl.settings.subtitle', '配置 AI 控制设备时使用的模型')}
                  </p>
                </div>
              </div>
              {showModelSettings ? (
                <ChevronUp className="w-5 h-5 text-gray-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
              )}
            </button>

            {showModelSettings && (
              <div className="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
                <div className="pt-4 space-y-4">
                  {/* Global Model Selection */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      <div className="flex items-center gap-2">
                        <Cpu className="w-4 h-4" />
                        {t('deviceControl.settings.globalModel', '全局控制模型')}
                      </div>
                    </label>
                    <div className="flex items-center gap-3">
                      <select
                        value={globalModelSelection}
                        onChange={(e) => setGlobalModelSelection(e.target.value)}
                        disabled={modelLoading}
                        className="flex-1 px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-colors disabled:opacity-50"
                      >
                        <option value="">{t('deviceControl.settings.selectModel', '选择模型')}</option>
                        {modelOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={handleSaveGlobalModel}
                        disabled={isSavingModel || modelLoading}
                        className="px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                      >
                        {isSavingModel && <Loader2 className="w-4 h-4 animate-spin" />}
                        {t('common.save', '保存')}
                      </button>
                    </div>
                    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                      {t('deviceControl.settings.globalModelHint', '未配置专属模型的设备将使用此模型进行 AI 控制')}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
                  <MonitorSmartphone className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {devices.length}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t('deviceControl.stats.total', '总设备')}
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-xl">
                  <Wifi className="w-5 h-5 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {onlineCount}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t('deviceControl.stats.online', '在线')}
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gray-100 dark:bg-gray-700 rounded-xl">
                  <WifiOff className="w-5 h-5 text-gray-500 dark:text-gray-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {offlineCount}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t('deviceControl.stats.offline', '离线')}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Filter Tabs */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                statusFilter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {t('deviceControl.filter.all', '全部')}
            </button>
            <button
              onClick={() => setStatusFilter('online')}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                statusFilter === 'online'
                  ? 'bg-green-600 text-white'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {t('deviceControl.filter.online', '在线')}
            </button>
            <button
              onClick={() => setStatusFilter('offline')}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                statusFilter === 'offline'
                  ? 'bg-gray-600 text-white'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {t('deviceControl.filter.offline', '离线')}
            </button>
          </div>

          {/* Error State */}
          {error && (
            <div className="flex items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl">
              <AlertCircle className="w-5 h-5 text-red-500" />
              <p className="text-red-600 dark:text-red-400">{error}</p>
              <button
                onClick={handleRefresh}
                className="ml-auto px-3 py-1 bg-red-100 dark:bg-red-900/30 hover:bg-red-200 dark:hover:bg-red-900/50 text-red-600 dark:text-red-400 rounded-lg text-sm font-medium transition-colors"
              >
                {t('common.retry', '重试')}
              </button>
            </div>
          )}

          {/* Device List */}
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <div
                  key={i}
                  className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5 animate-pulse"
                >
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-12 h-12 bg-gray-200 dark:bg-gray-700 rounded-xl" />
                    <div className="flex-1">
                      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2" />
                      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded" />
                    <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-2/3" />
                  </div>
                </div>
              ))}
            </div>
          ) : filteredDevices.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="p-4 bg-gray-100 dark:bg-gray-800 rounded-2xl mb-4">
                <MonitorSmartphone className="w-12 h-12 text-gray-400" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                {searchQuery || statusFilter !== 'all'
                  ? t('deviceControl.empty.noResults', '没有找到匹配的设备')
                  : t('deviceControl.empty.title', '还没有连接的设备')}
              </h3>
              <p className="text-gray-500 dark:text-gray-400 max-w-md mb-6">
                {searchQuery || statusFilter !== 'all'
                  ? t('deviceControl.empty.tryOther', '尝试其他搜索条件或筛选')
                  : t(
                      'deviceControl.empty.description',
                      '点击"添加设备"按钮生成绑定码，然后在控制端软件中输入绑定码来连接您的设备。'
                    )}
              </p>
              {!searchQuery && statusFilter === 'all' && (
                <button
                  onClick={() => setShowBindCodeModal(true)}
                  className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition-colors"
                >
                  <Plus className="w-5 h-5" />
                  {t('deviceControl.addDevice', '添加设备')}
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredDevices.map((device) => (
                <DeviceCard
                  key={device.id}
                  device={device}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                  onDisconnect={handleDisconnect}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <BindCodeModal
        isOpen={showBindCodeModal}
        onClose={() => setShowBindCodeModal(false)}
      />

      <EditDeviceModal
        isOpen={showEditModal}
        device={selectedDevice}
        onClose={() => {
          setShowEditModal(false);
          setSelectedDevice(null);
        }}
      />

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        title={t('deviceControl.delete.title', '确认删除')}
        message={t('deviceControl.delete.message', {
          name: deviceToDelete?.device_name,
          defaultValue: `确定要删除设备 "${deviceToDelete?.device_name}" 吗？此操作无法撤销。`,
        })}
        confirmText={t('common.delete', '删除')}
        cancelText={t('common.cancel', '取消')}
        confirmVariant="danger"
        onConfirm={handleDeleteConfirm}
        onCancel={() => {
          setShowDeleteConfirm(false);
          setDeviceToDelete(null);
        }}
        isLoading={isDeleting}
      />

      <ConfirmDialog
        isOpen={showDisconnectConfirm}
        title={t('deviceControl.disconnect.title', '确认断开')}
        message={t('deviceControl.disconnect.message', {
          name: deviceToDisconnect?.device_name,
          defaultValue: `确定要断开设备 "${deviceToDisconnect?.device_name}" 的连接吗？`,
        })}
        confirmText={t('deviceControl.device.disconnect', '断开连接')}
        cancelText={t('common.cancel', '取消')}
        confirmVariant="primary"
        onConfirm={handleDisconnectConfirm}
        onCancel={() => {
          setShowDisconnectConfirm(false);
          setDeviceToDisconnect(null);
        }}
        isLoading={isDisconnecting}
      />

      {/* Session Monitor Modal */}
      {showSessionMonitor && (
        <div className="fixed inset-0 z-50 overflow-hidden flex items-center justify-center p-4 sm:p-6">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-gray-900/60 dark:bg-black/80 backdrop-blur-sm transition-opacity animate-in fade-in duration-300"
            onClick={() => setShowSessionMonitor(false)}
          />

          {/* Modal */}
          <div className="relative bg-white dark:bg-gray-900 rounded-3xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-300">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-800 bg-gradient-to-r from-purple-600 to-indigo-600">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-white/10 backdrop-blur-md rounded-xl">
                  <Activity className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">
                    {t('deviceControl.sessionMonitor.modalTitle', 'Computer Use 会话监控')}
                  </h2>
                  <p className="text-purple-100 text-xs opacity-80">
                    {t('deviceControl.sessionMonitor.modalSubtitle', '实时查看 AI 控制设备的执行状态')}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowSessionMonitor(false)}
                className="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded-xl transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6">
              {monitoringSessionId ? (
                <ComputerUseSessionMonitor
                  sessionId={monitoringSessionId}
                  onClose={() => setMonitoringSessionId(null)}
                  autoRefresh={true}
                  refreshInterval={2000}
                />
              ) : (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-2xl mb-4">
                    <Activity className="w-12 h-12 text-purple-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                    {t('deviceControl.sessionMonitor.noSession', '暂无活动会话')}
                  </h3>
                  <p className="text-gray-500 dark:text-gray-400 max-w-md mb-6">
                    {t('deviceControl.sessionMonitor.noSessionDesc', '当 AI 员工开始控制设备执行任务时，您可以在此处实时监控执行进度和操作步骤。')}
                  </p>
                  <div className="flex flex-col gap-2 text-sm text-gray-500 dark:text-gray-400">
                    <p>💡 {t('deviceControl.sessionMonitor.tip1', '确保设备处于在线状态')}</p>
                    <p>🤖 {t('deviceControl.sessionMonitor.tip2', '在团队配置中添加远程代理')}</p>
                    <p>💬 {t('deviceControl.sessionMonitor.tip3', '通过对话让 AI 员工执行设备操作任务')}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
};

export default DeviceManagement;

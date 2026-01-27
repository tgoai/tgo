import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, Maximize2, Minimize2, Wifi, WifiOff, QrCode, AlertCircle } from 'lucide-react';
import { platformsApiService, VisionStatusResponse, VisionScreenshotResponse } from '@/services/platformsApi';

interface Props {
    platformId: string;
    isEnabled: boolean;
    onReconnect?: () => void;
}

/**
 * VisionAgentConsole - Displays real-time screen, status, and QR code for Vision Agent sessions.
 */
const VisionAgentConsole: React.FC<Props> = ({ platformId, isEnabled, onReconnect }) => {
    const { t } = useTranslation();
    
    const [status, setStatus] = useState<VisionStatusResponse | null>(null);
    const [screenshot, setScreenshot] = useState<VisionScreenshotResponse | null>(null);
    const [statusLoading, setStatusLoading] = useState(false);
    const [screenshotLoading, setScreenshotLoading] = useState(false);
    const [reconnecting, setReconnecting] = useState(false);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [error, setError] = useState<string | null>(null);
    
    const statusIntervalRef = useRef<any>(null);
    const screenshotIntervalRef = useRef<any>(null);

    // Fetch status
    const fetchStatus = useCallback(async () => {
        if (!isEnabled) return;
        setStatusLoading(true);
        try {
            const res = await platformsApiService.getVisionStatus(platformId);
            setStatus(res);
            setError(res.error || null);
        } catch (e) {
            console.error('Failed to fetch vision status', e);
            setError('Failed to fetch status');
        } finally {
            setStatusLoading(false);
        }
    }, [platformId, isEnabled]);

    // Fetch screenshot
    const fetchScreenshot = useCallback(async () => {
        if (!isEnabled) return;
        setScreenshotLoading(true);
        try {
            const res = await platformsApiService.getVisionScreenshot(platformId);
            setScreenshot(res);
            if (res.error && !error) {
                setError(res.error);
            }
        } catch (e) {
            console.error('Failed to fetch vision screenshot', e);
        } finally {
            setScreenshotLoading(false);
        }
    }, [platformId, isEnabled, error]);

    // Handle reconnect
    const handleReconnect = useCallback(async () => {
        setReconnecting(true);
        try {
            const res = await platformsApiService.reconnectVisionSession(platformId);
            setStatus(res);
            setError(res.error || null);
            // Refresh screenshot after reconnect
            setTimeout(() => fetchScreenshot(), 2000);
            onReconnect?.();
        } catch (e) {
            console.error('Failed to reconnect vision session', e);
            setError('Failed to reconnect');
        } finally {
            setReconnecting(false);
        }
    }, [platformId, fetchScreenshot, onReconnect]);

    // Start/stop polling based on isEnabled
    useEffect(() => {
        if (isEnabled) {
            // Initial fetch
            fetchStatus();
            fetchScreenshot();
            
            // Status polling: 5s when not logged in, 30s when logged in
            const startStatusPolling = () => {
                if (statusIntervalRef.current) clearInterval(statusIntervalRef.current);
                const interval = status?.login_status === 'logged_in' ? 30000 : 5000;
                statusIntervalRef.current = setInterval(fetchStatus, interval);
            };
            
            // Screenshot polling: 10s
            const startScreenshotPolling = () => {
                if (screenshotIntervalRef.current) clearInterval(screenshotIntervalRef.current);
                screenshotIntervalRef.current = setInterval(fetchScreenshot, 10000);
            };
            
            startStatusPolling();
            startScreenshotPolling();
        } else {
            // Clear when disabled
            if (statusIntervalRef.current) {
                clearInterval(statusIntervalRef.current);
                statusIntervalRef.current = null;
            }
            if (screenshotIntervalRef.current) {
                clearInterval(screenshotIntervalRef.current);
                screenshotIntervalRef.current = null;
            }
            setStatus(null);
            setScreenshot(null);
        }
        
        return () => {
            if (statusIntervalRef.current) clearInterval(statusIntervalRef.current);
            if (screenshotIntervalRef.current) clearInterval(screenshotIntervalRef.current);
        };
    }, [isEnabled, fetchStatus, fetchScreenshot, status?.login_status]);

    // Status badge color and text
    const getStatusBadge = () => {
        if (!status) return { color: 'bg-gray-400', text: t('vision.status.unknown', '未知') };
        
        switch (status.login_status) {
            case 'logged_in':
                return { color: 'bg-green-500', text: t('vision.status.loggedIn', '已登录'), icon: Wifi };
            case 'qr_pending':
                return { color: 'bg-yellow-500', text: t('vision.status.qrPending', '等待扫码'), icon: QrCode };
            case 'expired':
                return { color: 'bg-red-500', text: t('vision.status.expired', '会话过期'), icon: WifiOff };
            case 'offline':
            default:
                return { color: 'bg-gray-400', text: t('vision.status.offline', '离线'), icon: WifiOff };
        }
    };

    const statusBadge = getStatusBadge();
    const StatusIcon = statusBadge.icon || WifiOff;

    if (!isEnabled) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500 dark:text-gray-400">
                <WifiOff className="w-12 h-12 mb-3 opacity-50" />
                <p className="text-sm">{t('vision.disabled', '平台未启用')}</p>
                <p className="text-xs mt-1">{t('vision.enableHint', '启用平台后将显示实时画面')}</p>
            </div>
        );
    }

    return (
        <div className={`flex flex-col h-full ${isFullscreen ? 'fixed inset-0 z-50 bg-white dark:bg-gray-900 p-4' : ''}`}>
            {/* Header with status */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium text-white ${statusBadge.color}`}>
                        <StatusIcon className="w-3 h-3" />
                        {statusBadge.text}
                    </span>
                    {status?.message_poll_active && (
                        <span className="text-xs text-green-600 dark:text-green-400">
                            {t('vision.polling', '轮询中')}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => { fetchStatus(); fetchScreenshot(); }}
                        disabled={statusLoading || screenshotLoading}
                        className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                        title={t('vision.refresh', '刷新')}
                    >
                        <RefreshCw className={`w-4 h-4 text-gray-600 dark:text-gray-300 ${(statusLoading || screenshotLoading) ? 'animate-spin' : ''}`} />
                    </button>
                    <button
                        onClick={() => setIsFullscreen(!isFullscreen)}
                        className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        title={isFullscreen ? t('vision.exitFullscreen', '退出全屏') : t('vision.fullscreen', '全屏')}
                    >
                        {isFullscreen ? (
                            <Minimize2 className="w-4 h-4 text-gray-600 dark:text-gray-300" />
                        ) : (
                            <Maximize2 className="w-4 h-4 text-gray-600 dark:text-gray-300" />
                        )}
                    </button>
                </div>
            </div>

            {/* Error message */}
            {error && (
                <div className="mb-3 p-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded-md flex items-center gap-2 text-sm text-red-700 dark:text-red-300">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span className="flex-1">{error}</span>
                    <button
                        onClick={handleReconnect}
                        disabled={reconnecting}
                        className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                    >
                        {reconnecting ? t('vision.reconnecting', '重连中...') : t('vision.reconnect', '重新连接')}
                    </button>
                </div>
            )}

            {/* Main content area */}
            <div className="flex-1 flex flex-col lg:flex-row gap-4 min-h-0">
                {/* Screenshot preview */}
                <div className={`${status?.login_status === 'qr_pending' && status?.qr_code_base64 ? 'lg:w-2/3' : 'w-full'} flex flex-col min-h-0`}>
                    <div className="text-xs font-medium text-gray-600 dark:text-gray-300 mb-2">
                        {t('vision.screenPreview', '屏幕预览')}
                    </div>
                    <div className="flex-1 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden flex items-center justify-center min-h-[200px] relative">
                        {screenshot?.base64_image ? (
                            <img
                                src={`data:image/png;base64,${screenshot.base64_image}`}
                                alt="Screen"
                                className="max-w-full max-h-full object-contain"
                            />
                        ) : (
                            <div className="text-gray-400 dark:text-gray-500 text-sm text-center">
                                {screenshotLoading ? (
                                    <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2" />
                                ) : (
                                    <>
                                        <div className="w-16 h-16 mx-auto mb-2 rounded-lg bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
                                            <span className="text-2xl">📱</span>
                                        </div>
                                        {t('vision.noScreenshot', '暂无截图')}
                                    </>
                                )}
                            </div>
                        )}
                        {screenshotLoading && screenshot?.base64_image && (
                            <div className="absolute top-2 right-2">
                                <RefreshCw className="w-4 h-4 text-blue-500 animate-spin" />
                            </div>
                        )}
                    </div>
                    {screenshot?.timestamp && (
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            {t('vision.lastUpdate', '更新时间')}: {new Date(screenshot.timestamp).toLocaleString()}
                        </div>
                    )}
                </div>

                {/* QR Code area - only show when qr_pending */}
                {status?.login_status === 'qr_pending' && status?.qr_code_base64 && (
                    <div className="lg:w-1/3 flex flex-col">
                        <div className="text-xs font-medium text-gray-600 dark:text-gray-300 mb-2">
                            {t('vision.scanQR', '扫码登录')}
                        </div>
                        <div className="flex-1 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 flex flex-col items-center justify-center">
                            <img
                                src={`data:image/png;base64,${status.qr_code_base64}`}
                                alt="QR Code"
                                className="max-w-[200px] w-full"
                            />
                            <p className="text-sm text-gray-600 dark:text-gray-300 mt-3 text-center">
                                {t('vision.scanHint', '请使用微信扫描二维码登录')}
                            </p>
                        </div>
                    </div>
                )}
            </div>

            {/* Footer with session info */}
            <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500 dark:text-gray-400">
                <div className="flex items-center gap-4">
                    {status?.session_id && (
                        <span>Session: {status.session_id.slice(0, 8)}...</span>
                    )}
                    {status?.last_heartbeat && (
                        <span>{t('vision.lastHeartbeat', '心跳')}: {new Date(status.last_heartbeat).toLocaleTimeString()}</span>
                    )}
                </div>
                {status?.session_status === 'not_found' || status?.session_status === 'error' ? (
                    <button
                        onClick={handleReconnect}
                        disabled={reconnecting}
                        className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                    >
                        {reconnecting ? t('vision.reconnecting', '重连中...') : t('vision.reconnect', '重新连接')}
                    </button>
                ) : null}
            </div>
        </div>
    );
};

export default VisionAgentConsole;

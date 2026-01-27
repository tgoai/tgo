/**
 * BindCodeModal Component
 * Modal for generating and displaying device bind codes
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Copy, RefreshCw, Check, Monitor, Clock } from 'lucide-react';
import { useDeviceControlStore } from '@/stores/deviceControlStore';

interface BindCodeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const BindCodeModal: React.FC<BindCodeModalProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const [timeLeft, setTimeLeft] = useState<number>(0);

  const {
    bindCode,
    bindCodeExpiresAt,
    isGeneratingCode,
    generateBindCode,
    clearBindCode,
  } = useDeviceControlStore();

  // Generate code on open
  useEffect(() => {
    if (isOpen && !bindCode) {
      generateBindCode();
    }
  }, [isOpen, bindCode, generateBindCode]);

  // Countdown timer
  useEffect(() => {
    if (!bindCodeExpiresAt) return;

    const updateTimer = () => {
      const now = new Date().getTime();
      const expires = new Date(bindCodeExpiresAt).getTime();
      const diff = Math.max(0, Math.floor((expires - now) / 1000));
      setTimeLeft(diff);

      if (diff <= 0) {
        clearBindCode();
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [bindCodeExpiresAt, clearBindCode]);

  // Copy to clipboard
  const handleCopy = useCallback(async () => {
    if (!bindCode) return;
    try {
      await navigator.clipboard.writeText(bindCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  }, [bindCode]);

  // Refresh code
  const handleRefresh = useCallback(() => {
    clearBindCode();
    generateBindCode();
  }, [clearBindCode, generateBindCode]);

  // Close and cleanup
  const handleClose = useCallback(() => {
    clearBindCode();
    onClose();
  }, [clearBindCode, onClose]);

  // Format time
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-3xl w-full max-w-md shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
              <Monitor className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">
              {t('deviceControl.bindCode.title', '添加设备')}
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 text-center">
            {t('deviceControl.bindCode.description', '在控制端软件中输入以下绑定码来连接您的设备')}
          </p>

          {/* Bind Code Display */}
          <div className="bg-gray-50 dark:bg-gray-900 rounded-2xl p-6 mb-4">
            {isGeneratingCode ? (
              <div className="flex items-center justify-center py-4">
                <RefreshCw className="w-6 h-6 text-blue-600 animate-spin" />
              </div>
            ) : bindCode ? (
              <>
                <div className="flex items-center justify-center gap-2 mb-4">
                  {bindCode.split('').map((char, index) => (
                    <span
                      key={index}
                      className="w-12 h-14 flex items-center justify-center text-2xl font-mono font-bold bg-white dark:bg-gray-800 rounded-xl border-2 border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100"
                    >
                      {char}
                    </span>
                  ))}
                </div>

                {/* Timer */}
                <div className="flex items-center justify-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                  <Clock className="w-4 h-4" />
                  <span>
                    {t('deviceControl.bindCode.expiresIn', '有效期剩余')} {formatTime(timeLeft)}
                  </span>
                </div>
              </>
            ) : (
              <div className="text-center py-4 text-gray-500">
                {t('deviceControl.bindCode.expired', '绑定码已过期')}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={handleCopy}
              disabled={!bindCode || isGeneratingCode}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white rounded-xl font-medium transition-colors"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4" />
                  {t('common.copied', '已复制')}
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  {t('common.copy', '复制')}
                </>
              )}
            </button>
            <button
              onClick={handleRefresh}
              disabled={isGeneratingCode}
              className="px-4 py-3 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-xl font-medium transition-colors flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${isGeneratingCode ? 'animate-spin' : ''}`} />
              {t('common.refresh', '刷新')}
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 pb-6">
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-4">
            <h4 className="text-sm font-medium text-blue-800 dark:text-blue-200 mb-2">
              {t('deviceControl.bindCode.howTo', '如何连接？')}
            </h4>
            <ol className="text-sm text-blue-700 dark:text-blue-300 space-y-1 list-decimal list-inside">
              <li>{t('deviceControl.bindCode.step1', '下载并安装控制端软件')}</li>
              <li>{t('deviceControl.bindCode.step2', '打开软件并输入上方绑定码')}</li>
              <li>{t('deviceControl.bindCode.step3', '连接成功后设备将出现在列表中')}</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BindCodeModal;

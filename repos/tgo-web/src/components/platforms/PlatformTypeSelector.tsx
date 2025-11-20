import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import platformsApiService, { PlatformTypeDefinitionResponse } from '@/services/platformsApi';
import { getPlatformColor, getPlatformIconComponent, toPlatformType } from '@/utils/platformUtils';

interface PlatformTypeSelectorProps {
  open: boolean;
  onClose: () => void;
  onSelect: (type: { type: string; name: string }) => void;
}

const Loading: React.FC = () => {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-center py-10 text-sm text-gray-500">
      {t('platforms.typeSelector.loading', '正在加载可用平台类型...')}
    </div>
  );
};

const ErrorState: React.FC<{ message: string; onRetry: () => void }> = ({ message, onRetry }) => {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center justify-center py-10 text-sm text-red-600">
      <p className="mb-3">{message || t('platforms.typeSelector.loadError', '加载平台类型失败，请稍后重试')}</p>
      <button onClick={onRetry} className="px-3 py-1.5 text-white bg-red-500 hover:bg-red-600 rounded-md">
        {t('common.retry', '重试')}
      </button>
    </div>
  );
};

const PlatformTypeSelector: React.FC<PlatformTypeSelectorProps> = ({ open, onClose, onSelect }) => {
  const { t } = useTranslation();
  const [types, setTypes] = useState<PlatformTypeDefinitionResponse[] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Fetch when open
  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    const fetchTypes = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await platformsApiService.listPlatformTypes();
        if (!cancelled) setTypes(data);
      } catch (e: any) {
        const message = e?.getUserMessage?.() || e?.message || t('platforms.typeSelector.loadFailed', '加载失败');
        if (!cancelled) setError(message);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    fetchTypes();
    return () => { cancelled = true; };
  }, [open]);

  // Close on ESC
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30" />
      <div ref={dialogRef} className="relative bg-white rounded-xl shadow-2xl w-[560px] max-w-[90vw]">
        {/* Header */}
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-base font-semibold text-gray-800">
            {t('platforms.typeSelector.title', '选择接入平台类型')}
          </h3>
          <button onClick={onClose} className="p-1.5 text-gray-500 hover:bg-gray-100 rounded-md">✕</button>
        </div>

        {/* Body */}
        <div className="p-4">
          {isLoading && <Loading />}
          {!isLoading && error && <ErrorState message={error} onRetry={() => { setError(null); setIsLoading(true); platformsApiService.listPlatformTypes(true).then(setTypes).catch((e:any)=> setError(e?.getUserMessage?.()||e?.message||t('platforms.typeSelector.loadFailed', '加载失败'))).finally(()=> setIsLoading(false)); }} />}

          {!isLoading && !error && (
            <div className="grid grid-cols-2 gap-3">
              {types
                ?.filter((platformType) => platformType.is_supported !== false) // Only show supported types
                .map((platformType) => {
                  const displayName = platformType.display_name || platformType.name;

                  return (
                    <button
                      key={platformType.id}
                      onClick={() => {
                        onSelect({ type: platformType.type, name: platformType.name });
                      }}
                      className="p-3 border border-gray-200 rounded-lg transition flex items-start gap-3 text-left hover:border-blue-300 hover:bg-blue-50/50 cursor-pointer"
                    >
                      {/* Icon based on platform type (react-icons) */}
                      {(() => {
                        const type = toPlatformType(platformType.type as any);
                        const IconComp = getPlatformIconComponent(type);
                        return (
                          <span className="w-8 h-8 rounded flex items-center justify-center bg-gray-50">
                            <IconComp
                              size={20}
                              className={getPlatformColor(type)}
                            />
                          </span>
                        );
                      })()}
                      <div>
                        <div className="text-sm font-medium text-gray-800">
                          {displayName}
                        </div>
                        <div className="text-xs text-gray-500">{platformType.type}</div>
                      </div>
                    </button>
                  );
                })}
              {!types?.filter((platformType) => platformType.is_supported !== false).length && (
                <div className="col-span-2 text-center text-gray-500 py-8 text-sm">
                  {t('platforms.typeSelector.emptyTypes', '暂无可用平台类型')}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-gray-100 flex justify-end">
          <button onClick={onClose} className="px-3 py-1.5 rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50">
            {t('common.cancel', '取消')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PlatformTypeSelector;


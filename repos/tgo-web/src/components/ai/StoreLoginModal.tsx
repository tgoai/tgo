import React, { useEffect, useRef } from 'react';
import { X, Loader2, Sparkles, ExternalLink } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useStoreAuthStore } from '@/stores/storeAuthStore';
import { useToast } from './ToolToastProvider';
import { generateCodeVerifier, generateCodeChallenge } from '@/utils/pkce';
import storeApi from '@/services/storeApi';

interface StoreLoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const StoreLoginModal: React.FC<StoreLoginModalProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { exchangeCode, isLoading } = useStoreAuthStore();
  
  // 使用 Ref 保证 handleMessage 始终能访问最新的 exchangeCode 和 onClose
  const exchangeCodeRef = useRef(exchangeCode);
  const onCloseRef = useRef(onClose);
  const showToastRef = useRef(showToast);
  const tRef = useRef(t);

  useEffect(() => {
    exchangeCodeRef.current = exchangeCode;
    onCloseRef.current = onClose;
    showToastRef.current = showToast;
    tRef.current = t;
  }, [exchangeCode, onClose, showToast, t]);

  const handleOpenLogin = async () => {
    // 1. 先同步打开空白窗口（不会被拦截）
    const width = 520;
    const height = 680;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    
    const popup = window.open(
      'about:blank', 
      'toolstore_login', 
      `width=${width},height=${height},left=${left},top=${top},popup=yes`
    );

    if (!popup) {
      showToast('error', t('common.error'), t('tools.store.popupBlocked'));
      return;
    }

    try {
      // 2. 异步获取配置
      const config = await storeApi.getStoreConfig();
      const storeWebUrl = config.store_web_url || 'http://localhost:3002';

      // 3. 生成 PKCE 参数
      const codeVerifier = generateCodeVerifier();
      const codeChallenge = await generateCodeChallenge(codeVerifier);
      const state = crypto.randomUUID();
      
      sessionStorage.setItem('toolstore_pkce_verifier', codeVerifier);
      sessionStorage.setItem('toolstore_auth_state', state);
      
      const loginUrl = `${storeWebUrl}/auth/callback?` +
        `state=${state}&code_challenge=${codeChallenge}`;
      
      console.log('[StoreLoginModal] Navigating popup to:', loginUrl);
      
      // 4. 更新已打开窗口的 URL
      popup.location.href = loginUrl;
    } catch (error) {
      console.error('[StoreLoginModal] Failed to initiate login:', error);
      popup.close(); // 出错时关闭窗口
      showToast('error', t('common.error'), t('tools.store.model.initLoginFailed'));
    }
  };

  useEffect(() => {
    const messageHandler = async (event: MessageEvent) => {
      // 忽略来自非预期的 Origin 的消息（安全考虑）
      // if (event.origin !== TOOL_STORE_URLS.WEB) return; 

      const data = event.data;
      if (!data || data.type !== 'TOOLSTORE_AUTH_CODE') return;

      console.log('[StoreLoginModal] Received valid auth code message:', data);

      const savedState = sessionStorage.getItem('toolstore_auth_state');
      if (savedState && data.state !== savedState) {
        console.warn('[StoreLoginModal] Auth state mismatch:', { received: data.state, saved: savedState });
      }

      const codeVerifier = sessionStorage.getItem('toolstore_pkce_verifier');
      if (!codeVerifier) {
        console.error('[StoreLoginModal] Missing code verifier in sessionStorage');
        showToastRef.current('error', tRef.current('tools.store.loginFailed'), tRef.current('tools.store.model.missingVerifier'));
        return;
      }

      try {
        console.log('[StoreLoginModal] Exchanging code...');
        await exchangeCodeRef.current(data.code, codeVerifier);
        console.log('[StoreLoginModal] Login success!');
        showToastRef.current('success', tRef.current('tools.store.loginSuccess'), tRef.current('tools.store.loginSuccessDesc'));
        onCloseRef.current();
      } catch (err) {
        console.error('[StoreLoginModal] Exchange error:', err);
        showToastRef.current('error', tRef.current('tools.store.loginFailed'), tRef.current('tools.store.model.invalidCode'));
      } finally {
        sessionStorage.removeItem('toolstore_pkce_verifier');
        sessionStorage.removeItem('toolstore_auth_state');
      }
    };

    console.log('[StoreLoginModal] Global message listener active');
    window.addEventListener('message', messageHandler);
    return () => {
      window.removeEventListener('message', messageHandler);
    };
  }, []);

  // 注意：即使 isOpen 为 false，我们也不 return null，而是控制 UI 的可见性
  // 这样可以确保 useEffect 中的监听器始终处于活动状态
  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
          <div 
            className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm animate-in fade-in duration-300"
            onClick={onClose}
          />

          <div className="relative w-full max-w-md bg-white dark:bg-gray-900 rounded-[2.5rem] shadow-2xl overflow-hidden border border-gray-100 dark:border-gray-800 animate-in zoom-in-95 slide-in-from-bottom-8 duration-500">
            <div className="h-32 bg-gradient-to-br from-blue-600 to-indigo-700 relative overflow-hidden">
              <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-20"></div>
              
              <button 
                onClick={onClose}
                className="absolute top-4 right-4 p-2 bg-black/10 hover:bg-black/20 text-white rounded-full transition-colors z-10"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-16 h-16 bg-white dark:bg-gray-800 rounded-2xl shadow-xl flex items-center justify-center text-blue-600">
                  <Sparkles className="w-8 h-8" />
                </div>
              </div>
            </div>

            <div className="p-8 space-y-6">
              <div className="text-center space-y-2">
                <h2 className="text-2xl font-black text-gray-900 dark:text-gray-100 tracking-tight">
                  {t('tools.store.loginTitle')}
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {t('tools.store.loginRequiredDesc')}
                </p>
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 p-6 rounded-[2rem] border border-blue-100/50 dark:border-blue-800/30">
                <p className="text-sm font-bold text-blue-700 dark:text-blue-300 text-center mb-6 leading-relaxed">
                  {t('tools.store.loginSecurityDesc')}
                </p>
                
                <button
                  onClick={handleOpenLogin}
                  disabled={isLoading}
                  className="w-full py-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-black rounded-2xl shadow-xl shadow-blue-200 dark:shadow-none transition-all active:scale-[0.98] flex items-center justify-center gap-2 group"
                >
                  {isLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <ExternalLink className="w-5 h-5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                      {t('tools.store.openLoginWindow')}
                    </>
                  )}
                </button>
              </div>

              <div className="text-center">
                <p className="text-xs font-bold text-gray-400 leading-relaxed px-4">
                  {t('tools.store.loginSyncDesc')}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default StoreLoginModal;

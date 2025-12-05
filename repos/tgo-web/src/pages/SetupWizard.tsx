import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { setupApiService, SetupCheckResult } from '@/services/setupApi';
import { useSetupStore } from '@/stores/setupStore';
import { CheckCircle, XCircle, Loader2, Eye, EyeOff } from 'lucide-react';

// Types
interface AdminFormData {
  username: string;
  password: string;
  confirmPassword: string;
}

interface LLMFormData {
  provider: string;
  name: string;
  apiKey: string;
  apiBaseUrl: string;
  defaultModel: string;
  isActive: boolean;
}

interface ValidationErrors {
  password?: string;
  confirmPassword?: string;
  name?: string;
  apiKey?: string;
  general?: string;
}

type SetupStep = 1 | 2 | 3;

/**
 * Setup Wizard Page Component
 * Multi-step installation wizard for system initialization
 */
const SetupWizard: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { checkSetupStatus, hasAdmin } = useSetupStore();

  // Current step state
  const [currentStep, setCurrentStep] = useState<SetupStep>(1);

  // Form data
  const [adminData, setAdminData] = useState<AdminFormData>({
    username: 'admin', // Default username, not editable
    password: '',
    confirmPassword: '',
  });

  const [llmData, setLLMData] = useState<LLMFormData>({
    provider: 'none',
    name: '',
    apiKey: '',
    apiBaseUrl: '',
    defaultModel: '',
    isActive: true,
  });

  // UI state
  const [errors, setErrors] = useState<ValidationErrors>({});
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [verificationStatus, setVerificationStatus] = useState<any>(null);
  const [isVerifying, setIsVerifying] = useState(false);

  // Check if system is already installed and determine initial step
  useEffect(() => {
    const checkInstallation = async () => {
      try {
        const status = await setupApiService.getStatus();
        if (status.is_installed) {
          // System already installed, redirect to login
          navigate('/login', { replace: true });
        } else {
          // System not installed, determine which step to show
          if (!status.has_admin) {
            // No admin account yet, show step 1
            setCurrentStep(1);
          } else if (status.has_admin && !status.has_llm_config) {
            // Admin account exists but no LLM config, show step 2
            setCurrentStep(2);
          } else if (status.has_admin && status.has_llm_config) {
            // Both admin and LLM config exist, show step 3 (verification)
            setCurrentStep(3);
          }
        }
      } catch (error) {
        console.error('Failed to check installation status:', error);
        // On error, default to step 1
        setCurrentStep(1);
      }
    };
    checkInstallation();
  }, [navigate]);

  // Validate Step 1 (Admin Account)
  const validateAdminForm = (): boolean => {
    const newErrors: ValidationErrors = {};

    // Username is fixed as 'admin', no validation needed

    // Password validation
    if (!adminData.password) {
      newErrors.password = t('setup.admin.validation.passwordRequired');
    } else if (adminData.password.length < 8) {
      newErrors.password = t('setup.admin.validation.passwordLength');
    } else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(adminData.password)) {
      newErrors.password = t('setup.admin.validation.passwordStrength');
    }

    // Confirm password validation
    if (!adminData.confirmPassword) {
      newErrors.confirmPassword = t('setup.admin.validation.confirmPasswordRequired');
    } else if (adminData.password !== adminData.confirmPassword) {
      newErrors.confirmPassword = t('setup.admin.validation.passwordMismatch');
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Validate Step 2 (LLM Config) - optional
  const validateLLMForm = (): boolean => {
    if (llmData.provider === 'none') {
      return true; // Skip validation if not configuring
    }

    const newErrors: ValidationErrors = {};

    // Name is required
    if (!llmData.name.trim()) {
      newErrors.name = t('setup.llm.validation.nameRequired', 'Display name is required');
    }

    // API Key is required for non-local providers
    if (!llmData.apiKey && llmData.provider !== 'local') {
      newErrors.apiKey = t('setup.llm.validation.apiKeyRequired');
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle input changes
  const handleAdminInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setAdminData(prev => ({ ...prev, [name]: value }));
    // Clear error for this field
    if (errors[name as keyof ValidationErrors]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
    }
  };

  const handleLLMInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setLLMData(prev => ({ ...prev, [name]: value }));
    // Clear error for this field
    if (errors[name as keyof ValidationErrors]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
    }
  };

  // Handle Next button
  const handleNext = async () => {
    if (currentStep === 1) {
      if (!validateAdminForm()) return;

      setIsLoading(true);
      try {
        await setupApiService.createAdmin({
          username: adminData.username,
          password: adminData.password,
        });
        setCurrentStep(2);
      } catch (error: any) {
        setErrors({ general: error?.message || t('setup.errors.createAdminFailed') });
      } finally {
        setIsLoading(false);
      }
    } else if (currentStep === 2) {
      if (!validateLLMForm()) return;

      setIsLoading(true);
      try {
        if (llmData.provider === 'none') {
          // Call skip-llm API when user selects "none" and clicks next
          await setupApiService.skipLLM();
        } else {
          // Configure LLM when user selects a provider
          await setupApiService.configureLLM({
            provider: llmData.provider,
            name: llmData.name,
            api_key: llmData.apiKey,
            api_base_url: llmData.apiBaseUrl || undefined,
            default_model: llmData.defaultModel || undefined,
            is_active: llmData.isActive,
          });
        }
      } catch (error: any) {
        setErrors({ apiKey: error?.message || t('setup.errors.configureLLMFailed') });
        setIsLoading(false);
        return;
      } finally {
        setIsLoading(false);
      }

      setCurrentStep(3);
      // Trigger verification
      verifyInstallation();
    }
  };

  // Handle Previous button
  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep((currentStep - 1) as SetupStep);
    }
  };

  // Handle Skip button (Step 2 only)
  const handleSkip = async () => {
    if (currentStep === 2) {
      setIsLoading(true);
      try {
        // Call skip-llm API
        await setupApiService.skipLLM();
        setCurrentStep(3);
        verifyInstallation();
      } catch (error: any) {
        console.error('Failed to skip LLM configuration:', error);
        // Even if the API call fails, we still proceed to the next step
        setCurrentStep(3);
        verifyInstallation();
      } finally {
        setIsLoading(false);
      }
    }
  };

  // Verify installation
  const verifyInstallation = async () => {
    setIsVerifying(true);
    try {
      const result = await setupApiService.verify();
      setVerificationStatus(result);
    } catch (error) {
      console.error('Verification failed:', error);
      setVerificationStatus({
        is_valid: false,
        checks: {
          database: { passed: false, message: 'Connection failed' },
          admin: { passed: false, message: 'Verification failed' },
          llm: { passed: false, message: 'Not configured' },
        },
        errors: ['Verification failed'],
      });
    } finally {
      setIsVerifying(false);
    }
  };

  // Handle Finish button
  const handleFinish = async () => {
    // Refresh setup status to update the global state
    try {
      await checkSetupStatus();
      console.log('✅ Setup status refreshed after installation');
    } catch (error) {
      console.error('❌ Failed to refresh setup status:', error);
    }

    // Redirect to login page
    setTimeout(() => {
      navigate('/login', { replace: true });
    }, 2000);
  };

  // Render Step 1: Admin Account
  const renderAdminStep = () => (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-semibold text-gray-800 dark:text-gray-100 mb-2">
          {t('setup.admin.title')}
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">{t('setup.admin.description')}</p>
      </div>

      {/* General Error Message */}
      {errors.general && (
        <div className="p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded-md">
          <p className="text-sm text-red-600 dark:text-red-400">{errors.general}</p>
        </div>
      )}

      {/* Username - Fixed as 'admin' */}
      <div>
        <label htmlFor="username" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
          {t('setup.admin.username')}
        </label>
        <input
          type="text"
          id="username"
          name="username"
          value={adminData.username}
          readOnly
          className="w-full px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-gray-100 dark:bg-gray-600 text-gray-700 dark:text-gray-300 cursor-not-allowed"
        />
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          {t('setup.admin.usernameFixed', '默认管理员用户名，不可修改')}
        </p>
      </div>

      {/* Password */}
      <div>
        <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
          {t('setup.admin.password')}
        </label>
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'}
            id="password"
            name="password"
            value={adminData.password}
            onChange={handleAdminInputChange}
            className={`w-full px-4 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-100 ${
              errors.password ? 'border-red-300 bg-red-50 dark:border-red-600 dark:bg-red-950' : 'border-gray-300 dark:border-gray-600'
            }`}
            placeholder={t('setup.admin.passwordPlaceholder')}
            disabled={isLoading}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        {errors.password && (
          <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.password}</p>
        )}
      </div>

      {/* Confirm Password */}
      <div>
        <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
          {t('setup.admin.confirmPassword')}
        </label>
        <div className="relative">
          <input
            type={showConfirmPassword ? 'text' : 'password'}
            id="confirmPassword"
            name="confirmPassword"
            value={adminData.confirmPassword}
            onChange={handleAdminInputChange}
            className={`w-full px-4 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-100 ${
              errors.confirmPassword ? 'border-red-300 bg-red-50 dark:border-red-600 dark:bg-red-950' : 'border-gray-300 dark:border-gray-600'
            }`}
            placeholder={t('setup.admin.confirmPasswordPlaceholder')}
            disabled={isLoading}
          />
          <button
            type="button"
            onClick={() => setShowConfirmPassword(!showConfirmPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
          >
            {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        {errors.confirmPassword && (
          <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.confirmPassword}</p>
        )}
      </div>
    </div>
  );

  // Render Step 2: LLM Configuration
  const renderLLMStep = () => (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-semibold text-gray-800 dark:text-gray-100 mb-2">
          {t('setup.llm.title')}
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          {t('setup.llm.description')} <span className="text-gray-400 dark:text-gray-500">{t('setup.llm.optional')}</span>
        </p>
      </div>

      {/* Provider Selection */}
      <div>
        <label htmlFor="provider" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
          {t('setup.llm.provider')}
        </label>
        <select
          id="provider"
          name="provider"
          value={llmData.provider}
          onChange={handleLLMInputChange}
          className="w-full px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-100"
          disabled={isLoading}
        >
          <option value="none">{t('setup.llm.providers.none')}</option>
          <option value="openai">{t('setup.llm.providers.openai')}</option>
          <option value="azure">{t('setup.llm.providers.azure')}</option>
          <option value="anthropic">{t('setup.llm.providers.anthropic')}</option>
          <option value="local">{t('setup.llm.providers.local')}</option>
          <option value="other">{t('setup.llm.providers.other')}</option>
        </select>
      </div>

      {/* Conditional fields based on provider */}
      {llmData.provider !== 'none' && (
        <>
          {/* Display Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
              {t('setup.llm.name', 'Display Name')}
            </label>
            <input
              type="text"
              id="name"
              name="name"
              value={llmData.name}
              onChange={handleLLMInputChange}
              className={`w-full px-4 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-100 ${
                errors.name ? 'border-red-300 bg-red-50 dark:border-red-600 dark:bg-red-950' : 'border-gray-300 dark:border-gray-600'
              }`}
              placeholder={t('setup.llm.namePlaceholder', 'e.g., My OpenAI Provider')}
              disabled={isLoading}
            />
            {errors.name && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.name}</p>
            )}
          </div>

          {/* API Key */}
          {llmData.provider !== 'local' && (
            <div>
              <label htmlFor="apiKey" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                {t('setup.llm.apiKey')}
              </label>
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  id="apiKey"
                  name="apiKey"
                  value={llmData.apiKey}
                  onChange={handleLLMInputChange}
                  className={`w-full px-4 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-100 ${
                    errors.apiKey ? 'border-red-300 bg-red-50 dark:border-red-600 dark:bg-red-950' : 'border-gray-300 dark:border-gray-600'
                  }`}
                  placeholder={t('setup.llm.apiKeyPlaceholder')}
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
                >
                  {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.apiKey && (
                <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.apiKey}</p>
              )}
            </div>
          )}

          {/* API Base URL */}
          <div>
            <label htmlFor="apiBaseUrl" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
              {t('setup.llm.apiEndpoint')}
            </label>
            <input
              type="text"
              id="apiBaseUrl"
              name="apiBaseUrl"
              value={llmData.apiBaseUrl}
              onChange={handleLLMInputChange}
              className="w-full px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-100"
              placeholder={t('setup.llm.apiEndpointPlaceholder')}
              disabled={isLoading}
            />
          </div>

          {/* Default Model */}
          <div>
            <label htmlFor="defaultModel" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
              {t('setup.llm.model')}
            </label>
            <input
              type="text"
              id="defaultModel"
              name="defaultModel"
              value={llmData.defaultModel}
              onChange={handleLLMInputChange}
              className="w-full px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-100"
              placeholder={t('setup.llm.modelPlaceholder')}
              disabled={isLoading}
            />
          </div>
        </>
      )}
    </div>
  );

  // Render Step 3: Verification
  const renderVerifyStep = () => (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-semibold text-gray-800 dark:text-gray-100 mb-2">
          {t('setup.verify.title')}
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">{t('setup.verify.description')}</p>
      </div>

      {/* Installation Summary */}
      <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg p-4 space-y-2">
        <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-3">
          {t('setup.verify.summary')}
        </h3>
        <div className="flex items-center text-sm text-blue-800 dark:text-blue-300">
          <CheckCircle className="w-4 h-4 mr-2 text-green-600 dark:text-green-400" />
          {t('setup.verify.adminCreated')}: <span className="font-medium ml-1">{adminData.username}</span>
        </div>
        <div className="flex items-center text-sm text-blue-800 dark:text-blue-300">
          {llmData.provider !== 'none' ? (
            <>
              <CheckCircle className="w-4 h-4 mr-2 text-green-600 dark:text-green-400" />
              {t('setup.verify.llmConfigured')}: <span className="font-medium ml-1">{llmData.provider}</span>
            </>
          ) : (
            <>
              <XCircle className="w-4 h-4 mr-2 text-yellow-600 dark:text-yellow-400" />
              {t('setup.verify.llmNotConfigured')}
            </>
          )}
        </div>
      </div>

      {/* System Checks */}
      <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
          {t('setup.verify.checks.title')}
        </h3>

        {isVerifying ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-blue-600 dark:text-blue-400 mr-2" />
            <span className="text-sm text-gray-600 dark:text-gray-400">{t('setup.verify.verifying')}</span>
          </div>
        ) : verificationStatus ? (
          <div className="space-y-3">
            {/* Render all checks dynamically */}
            {Object.entries(verificationStatus.checks).map(([checkName, checkResult]) => {
              const result = checkResult as SetupCheckResult;
              return (
                <div key={checkName} className="flex items-center justify-between">
                  <span className="text-sm text-gray-700 dark:text-gray-300 capitalize">{checkName}</span>
                  <div className="flex items-center">
                    {result.passed ? (
                      <>
                        <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400 mr-1" />
                        <span className="text-xs text-green-600 dark:text-green-400">{t('setup.verify.checks.status.success')}</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-4 h-4 text-red-600 dark:text-red-400 mr-1" />
                        <span className="text-xs text-red-600 dark:text-red-400">{t('setup.verify.checks.status.failed')}</span>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>

      {/* Success Message */}
      {verificationStatus?.is_valid && (
        <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded-lg p-4 text-center">
          <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400 mx-auto mb-2" />
          <p className="text-sm font-semibold text-green-900 dark:text-green-200 mb-1">
            {t('setup.verify.installationComplete')}
          </p>
          <p className="text-xs text-green-700 dark:text-green-400">{t('setup.verify.redirecting')}</p>
        </div>
      )}

      {/* Error Messages */}
      {verificationStatus?.errors && verificationStatus.errors.length > 0 && (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded-lg p-4">
          <p className="text-sm font-semibold text-red-900 dark:text-red-200 mb-2">
            {t('setup.verify.verifyFailed')}
          </p>
          <ul className="list-disc list-inside space-y-1">
            {verificationStatus.errors.map((error: string, index: number) => (
              <li key={index} className="text-xs text-red-700 dark:text-red-400">{error}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );

  // Main render
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Logo and Title */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <img src="/logo.svg" alt="Tgo CS Logo" className="w-12 h-12" />
          </div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100 mb-2">{t('setup.title')}</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">{t('setup.subtitle')}</p>
        </div>

        {/* Step Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-center space-x-4">
            {[1, 2, 3].map((step) => (
              <div key={step} className="flex items-center">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold ${
                    currentStep === step
                      ? 'bg-blue-600 text-white'
                      : currentStep > step
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                  }`}
                >
                  {currentStep > step ? <CheckCircle className="w-5 h-5" /> : step}
                </div>
                {step < 3 && (
                  <div
                    className={`w-16 h-1 mx-2 ${
                      currentStep > step ? 'bg-green-600' : 'bg-gray-200 dark:bg-gray-700'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="text-center mt-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {t('setup.stepIndicator', { current: currentStep, total: 3 })}
            </p>
          </div>
        </div>

        {/* Main Card */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8">
          {/* Step Content */}
          {currentStep === 1 && renderAdminStep()}
          {currentStep === 2 && renderLLMStep()}
          {currentStep === 3 && renderVerifyStep()}

          {/* Navigation Buttons */}
          <div className="mt-8 flex items-center justify-between">
            {/* Previous Button */}
            {/* Only show "Previous" button if we're on step 2 and admin hasn't been created yet */}
            {currentStep === 2 && !hasAdmin && (
              <button
                onClick={handlePrevious}
                disabled={isLoading}
                className="px-6 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t('setup.buttons.previous')}
              </button>
            )}

            <div className="flex-1" />

            {/* Skip Button (Step 2 only) */}
            {currentStep === 2 && (
              <button
                onClick={handleSkip}
                disabled={isLoading}
                className="px-6 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 disabled:opacity-50 disabled:cursor-not-allowed mr-3"
              >
                {t('setup.buttons.skip')}
              </button>
            )}

            {/* Next/Finish Button */}
            {currentStep < 3 ? (
              <button
                onClick={handleNext}
                disabled={isLoading}
                className="px-6 py-2 text-sm font-medium text-white bg-blue-600 dark:bg-blue-700 rounded-md hover:bg-blue-700 dark:hover:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
              >
                {isLoading && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                {t('setup.buttons.next')}
              </button>
            ) : (
              <button
                onClick={handleFinish}
                disabled={!verificationStatus?.is_valid}
                className="px-6 py-2 text-sm font-medium text-white bg-green-600 dark:bg-green-700 rounded-md hover:bg-green-700 dark:hover:bg-green-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t('setup.buttons.finish')}
              </button>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-6">
          <p className="text-xs text-gray-500 dark:text-gray-400">{t('footer.copyright')}</p>
        </div>
      </div>
    </div>
  );
};

export default SetupWizard;


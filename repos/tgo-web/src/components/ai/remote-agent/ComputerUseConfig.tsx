/**
 * Computer Use Configuration Component
 * Configuration panel for Computer Use Agent settings
 */

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Monitor, HelpCircle } from 'lucide-react';
import Select from '@/components/ui/Select';
import { listDevices } from '@/services/deviceControlApi';
import type { Device } from '@/types/deviceControl';
import type { RemoteAgentTeamConfig } from '@/types/remoteAgent';

interface ComputerUseConfigProps {
  config: Partial<RemoteAgentTeamConfig>;
  onChange: (config: Partial<RemoteAgentTeamConfig>) => void;
}

export function ComputerUseConfig({ config, onChange }: ComputerUseConfigProps) {
  const { t } = useTranslation();
  const [devices, setDevices] = useState<Device[]>([]);
  const [loadingDevices, setLoadingDevices] = useState(true);

  useEffect(() => {
    const fetchDevices = async () => {
      try {
        const response = await listDevices({ status: 'online' });
        setDevices(response.devices || []);
      } catch (error) {
        console.error('Failed to fetch devices:', error);
      } finally {
        setLoadingDevices(false);
      }
    };

    fetchDevices();
  }, []);

  const handleChange = (key: keyof RemoteAgentTeamConfig, value: any) => {
    onChange({ ...config, [key]: value });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 pb-2 border-b">
        <Monitor className="w-5 h-5 text-blue-600" />
        <h4 className="font-medium">
          {t('computerUse.configTitle', 'Computer Use Configuration')}
        </h4>
      </div>

      {/* Device Selection */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">
            {t('computerUse.device', 'Bind Device')}
          </label>
          <div className="group relative">
            <HelpCircle className="w-4 h-4 text-gray-400 cursor-help" />
            <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-gray-800 text-white text-xs rounded shadow-lg z-50">
              {t(
                'computerUse.deviceHelp',
                'Select a device for the agent to control. If not selected, the first online device will be used.'
              )}
            </div>
          </div>
        </div>

        {loadingDevices ? (
          <div className="h-10 w-full bg-gray-100 animate-pulse rounded-lg" />
        ) : (
          <Select
            value={config.device_id || ''}
            onChange={(value: string) =>
              handleChange('device_id', value || undefined)
            }
            options={[
              { value: '', label: t('computerUse.autoSelect', 'Auto-select (first online device)') },
              ...devices.map(device => ({
                value: device.id,
                label: `${device.device_name} (${device.device_type})`
              }))
            ]}
          />
        )}
        {devices.length === 0 && !loadingDevices && (
          <p className="text-sm text-amber-600">
            {t(
              'computerUse.noDevices',
              'No online devices found. Please connect a device first.'
            )}
          </p>
        )}
      </div>

      {/* Max Rounds */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">
            {t('computerUse.maxRounds', 'Max Execution Rounds')}
          </label>
          <div className="group relative">
            <HelpCircle className="w-4 h-4 text-gray-400 cursor-help" />
            <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-gray-800 text-white text-xs rounded shadow-lg z-50">
              {t(
                'computerUse.maxRoundsHelp',
                'Maximum number of action rounds before stopping. Each round includes screenshot, analysis, and action execution.'
              )}
            </div>
          </div>
        </div>
        <input
          id="max_rounds"
          type="number"
          min={1}
          max={50}
          value={config.max_rounds || 20}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            handleChange('max_rounds', parseInt(e.target.value, 10) || 20)
          }
          className="w-32 border rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <p className="text-xs text-gray-500">
          {t('computerUse.maxRoundsDefault', 'Default: 20 rounds')}
        </p>
      </div>

      {/* Grounding Model */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">
            {t('computerUse.groundingModel', 'Element Localization Model')}
          </label>
          <div className="group relative">
            <HelpCircle className="w-4 h-4 text-gray-400 cursor-help" />
            <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-gray-800 text-white text-xs rounded shadow-lg z-50">
              {t(
                'computerUse.groundingModelHelp',
                'Model used to locate UI elements on screen. UI-TARS offers higher accuracy but requires separate deployment.'
              )}
            </div>
          </div>
        </div>
        <Select
          value={config.grounding_model || 'openai'}
          onChange={(value: string) =>
            handleChange('grounding_model', value)
          }
          options={[
            { value: 'openai', label: 'OpenAI GPT-4o' },
            { value: 'uitars', label: 'UI-TARS' }
          ]}
        />
      </div>

      {/* Summary */}
      <div className="p-4 bg-gray-50 rounded-lg">
        <h5 className="text-sm font-medium mb-2">
          {t('computerUse.summary', 'Configuration Summary')}
        </h5>
        <div className="text-sm text-gray-600 space-y-1">
          <p>
            <span className="font-medium">
              {t('computerUse.device', 'Device')}:
            </span>{' '}
            {config.device_id
              ? devices.find((d) => d.id === config.device_id)?.device_name ||
                config.device_id
              : t('computerUse.autoSelect', 'Auto-select')}
          </p>
          <p>
            <span className="font-medium">
              {t('computerUse.maxRounds', 'Max Rounds')}:
            </span>{' '}
            {config.max_rounds || 20}
          </p>
          <p>
            <span className="font-medium">
              {t('computerUse.groundingModel', 'Grounding Model')}:
            </span>{' '}
            {config.grounding_model === 'uitars' ? 'UI-TARS' : 'OpenAI GPT-4o'}
          </p>
        </div>
      </div>
    </div>
  );
}

export default ComputerUseConfig;

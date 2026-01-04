import React from 'react';
import { X } from 'lucide-react';
import { usePluginStore } from '@/stores/pluginStore';
import PluginTemplateRenderer from './PluginTemplateRenderer';
import { createPortal } from 'react-dom';

const PluginModal: React.FC = () => {
  const activeModal = usePluginStore((state) => state.activeModal);
  const closePluginModal = usePluginStore((state) => state.closePluginModal);

  if (!activeModal) return null;

  return createPortal(
    <div className="fixed inset-0 z-[1100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/40 backdrop-blur-sm" 
        onClick={closePluginModal}
      />
      
      {/* Modal Content */}
      <div className="relative w-full max-w-lg bg-white dark:bg-gray-800 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-gray-700">
          <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
            {activeModal.title}
          </h3>
          <button
            onClick={closePluginModal}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors text-gray-500 dark:text-gray-400"
          >
            <X size={20} />
          </button>
        </div>
        
        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          <PluginTemplateRenderer
            pluginId={activeModal.pluginId}
            template={activeModal.ui.template}
            data={activeModal.ui.data}
            context={activeModal.context}
          />
        </div>
      </div>
    </div>,
    document.body
  );
};

export default PluginModal;


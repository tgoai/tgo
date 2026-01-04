import React from 'react';
import KeyValueTemplate from './templates/KeyValueTemplate';
import TableTemplate from './templates/TableTemplate';
import FormTemplate from './templates/FormTemplate';
import ButtonTemplate from './templates/ButtonTemplate';
import { usePluginStore } from '@/stores/pluginStore';

interface PluginTemplateRendererProps {
  pluginId: string;
  template: string;
  data: any;
  context: any;
}

const TabsTemplate: React.FC<{
  data: any;
  pluginId: string;
  context: any;
}> = ({ data, pluginId, context }) => {
  const [activeTab, setActiveTab] = React.useState(data.default_tab || data.items?.[0]?.key);
  const currentTab = data.items?.find((it: any) => it.key === activeTab);

  return (
    <div className="space-y-4">
      <div className="flex border-b border-gray-100 dark:border-gray-700 overflow-x-auto">
        {data.items?.map((tab: any) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px whitespace-nowrap ${
              activeTab === tab.key
                ? 'text-blue-600 border-blue-600'
                : 'text-gray-500 border-transparent hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {currentTab && (
        <PluginTemplateRenderer
          pluginId={pluginId}
          template={currentTab.content.template}
          data={currentTab.content.data}
          context={context}
        />
      )}
    </div>
  );
};

const PluginTemplateRenderer: React.FC<PluginTemplateRendererProps> = ({
  pluginId,
  template,
  data,
  context,
}) => {
  const sendPluginEvent = usePluginStore((state) => state.sendPluginEvent);
  const closePluginModal = usePluginStore((state) => state.closePluginModal);

  if (!template || !data) return null;

  switch (template) {
    case 'key_value':
      return <KeyValueTemplate {...data} />;
    
    case 'table':
      return <TableTemplate {...data} />;
    
    case 'form':
      return (
        <FormTemplate
          {...data}
          onSubmit={(formData) =>
            sendPluginEvent(pluginId, 'form_submit', data.action_id || 'submit', context, formData)
          }
          onCancel={context.is_modal ? closePluginModal : undefined}
        />
      );
    
    case 'button':
      return (
        <ButtonTemplate
          {...data}
          onClick={(actionId) =>
            sendPluginEvent(pluginId, 'button_click', actionId, context)
          }
        />
      );
    
    case 'group':
      const isHorizontal = data.layout === 'horizontal';
      return (
        <div className={isHorizontal ? "flex flex-wrap gap-3" : "space-y-6"}>
          {data.items?.map((item: any, idx: number) => (
            <PluginTemplateRenderer
              key={idx}
              pluginId={pluginId}
              template={item.template}
              data={item.data}
              context={context}
            />
          ))}
        </div>
      );

    case 'tabs':
      return <TabsTemplate data={data} pluginId={pluginId} context={context} />;

    case 'text':
      return (
        <div className={`text-sm text-gray-700 dark:text-gray-300 ${data.type === 'markdown' ? 'prose dark:prose-invert prose-xs max-w-none' : ''}`}>
          {data.text}
        </div>
      );

    default:
      return (
        <div className="p-4 border border-dashed border-gray-200 dark:border-gray-700 rounded-lg text-center text-xs text-gray-400 italic">
          Unknown template: {template}
        </div>
      );
  }
};

export default PluginTemplateRenderer;


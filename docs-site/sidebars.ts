import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'category',
      label: '快速开始',
      collapsed: false,
      items: [
        {
          type: 'doc',
          id: 'intro',
          label: '介绍',
        },
        {
          type: 'doc',
          id: 'quick-start/deploy',
          label: '一键部署',
        },
        {
          type: 'doc',
          id: 'quick-start/faq',
          label: '常见问题',
        },
      ],
    },
    {
      type: 'category',
      label: '配置',
      collapsed: false,
      items: [
        {
          type: 'doc',
          id: 'config/env-vars',
          label: '环境变量',
        },
        {
          type: 'doc',
          id: 'config/domain-ssl',
          label: '配置域名和证书',
        },
      ],
    },
    {
      type: 'category',
      label: '开发',
      collapsed: false,
      items: [
        {
          type: 'doc',
          id: 'development/source-deploy',
          label: '源码部署',
        },
        {
          type: 'doc',
          id: 'development/restart-upgrade',
          label: '重启和升级',
        },
        {
          type: 'doc',
          id: 'development/debug-tools',
          label: '调试工具',
        },
        {
          type: 'doc',
          id: 'development/tgo-command',
          label: 'tgo 命令',
        },
      ],
    },
  ],
};

export default sidebars;

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import checker from 'vite-plugin-checker'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // TypeScript type checking in dev mode
    checker({
      typescript: {
        tsconfigPath: './tsconfig.json',
        buildMode: false, // Only check in dev mode
      },
      overlay: {
        initialIsOpen: false, // Don't auto-open overlay on start
        position: 'br', // bottom-right
        badgeStyle: 'margin: 0 0 20px 20px;',
      },
      enableBuild: false, // Disable in build mode (tsc already runs)
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      'saas-routes': process.env.VITE_EDITION === 'saas' 
        ? path.resolve(__dirname, '../../../saas-extensions/tgo-web-saas/src/routes.tsx')
        : path.resolve(__dirname, './src/saas-routes.ts'),
      'react': path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
      'react/jsx-runtime': path.resolve(__dirname, 'node_modules/react/jsx-runtime'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          // React core libraries + react-i18next (must be together)
          if (id.includes('node_modules/react/') ||
              id.includes('node_modules/react-dom/') ||
              id.includes('node_modules/scheduler/') ||
              id.includes('node_modules/react-i18next')) {
            return 'vendor-react';
          }

          // React Router
          if (id.includes('node_modules/react-router') ||
              id.includes('node_modules/@remix-run/router')) {
            return 'vendor-router';
          }

          // Internationalization (i18next core only, without react-i18next)
          if (id.includes('node_modules/i18next') &&
              !id.includes('node_modules/react-i18next')) {
            return 'vendor-i18n';
          }

          // Lucide React icons (large library)
          if (id.includes('node_modules/lucide-react')) {
            return 'vendor-lucide';
          }

          // React Icons (large library)
          if (id.includes('node_modules/react-icons')) {
            return 'vendor-react-icons';
          }

          // Markdown and code highlighting
          if (id.includes('node_modules/marked') ||
              id.includes('node_modules/highlight.js')) {
            return 'vendor-markdown';
          }

          // UI components
          if (id.includes('node_modules/react-easy-crop') ||
              id.includes('node_modules/yet-another-react-lightbox') ||
              id.includes('node_modules/dompurify')) {
            return 'vendor-ui';
          }

          // Miscellaneous dependencies
          if (id.includes('node_modules/zustand') ||
              id.includes('node_modules/easyjssdk') ||
              id.includes('node_modules/js-yaml') ||
              id.includes('node_modules/openapi-types')) {
            return 'vendor-misc';
          }

          // Split large application code by directory
          if (id.includes('/src/pages/')) {
            return 'app-pages';
          }

          if (id.includes('/src/components/')) {
            return 'app-components';
          }

          // Don't manually chunk stores - let Vite handle dependencies
          // to avoid initialization order issues
          // if (id.includes('/src/stores/')) {
          //   return 'app-stores';
          // }

          if (id.includes('/src/services/')) {
            return 'app-services';
          }
        },
      },
    },
    // Increase chunk size warning limit to 1000 kB
    chunkSizeWarningLimit: 1000,
  },
})

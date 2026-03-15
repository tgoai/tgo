import "../global.css";
import { RootProvider } from "fumadocs-ui/provider/next";
import { Inter } from "next/font/google";
import { defineI18nUI } from "fumadocs-ui/i18n";
import { i18n } from "@/lib/i18n";

export const metadata = {
  title: "TGO",
  description:
    "开源智能客服系统文档（多智能体 · 知识库 · MCP 工具 · 多渠道接入）",
  icons: {
    icon: "/logo.svg",
  },
  keywords: [
    "TGO",
    "AI智能客服",
    "智能客服",
    "多智能体",
    "知识库",
    "MCP 工具",
    "多渠道接入",
  ],
};

const { provider } = defineI18nUI(i18n, {
  translations: {
    en: {
      displayName: "English",
      search: "Search",
      searchNoResult: "No results found",
      toc: "Table of Contents",
      tocNoHeadings: "No headings",
      lastUpdate: "Last updated on",
      chooseLanguage: "Choose language",
      nextPage: "Next page",
      previousPage: "Previous page",
      chooseTheme: "Choose theme",
      editOnGithub: "Edit on GitHub",
    },
    zh: {
      displayName: "简体中文",
      search: "搜索文档",
      searchNoResult: "没有找到结果",
      toc: "目录",
      tocNoHeadings: "没有标题",
      lastUpdate: "最后更新于",
      chooseLanguage: "选择语言",
      nextPage: "下一页",
      previousPage: "上一页",
      chooseTheme: "选择主题",
      editOnGithub: "在 GitHub 上编辑",
    },
  },
});

const inter = Inter({
  subsets: ["latin"],
});

export default async function Layout({
  params,
  children,
}: {
  params: Promise<{ lang: string }>;
  children: React.ReactNode;
}) {
  const lang = (await params).lang;
  return (
    <html lang={lang} className={inter.className} suppressHydrationWarning>
      <body
        className="flex flex-col min-h-screen"
        data-pagefind-filter={`lang:${lang}`}
      >
        <RootProvider i18n={provider(lang)}>{children}</RootProvider>
      </body>
      <script
        src="https://widget.tgo-ai.com/tgo-widget-sdk.js?api_key=ak_live_qIMhQRx5klxuRHZkDke9HqZC3wi9sB43"
        async
      ></script>
    </html>
  );
}

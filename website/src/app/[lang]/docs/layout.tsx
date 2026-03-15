import type { ReactNode } from "react";
import { source } from "@/lib/source";
import { DocsLayout } from "fumadocs-ui/layouts/notebook";
import { baseOptions } from "@/lib/layout.shared";
import { useI18n } from "@/hooks/useI18n";
import type { Locale } from "@/i18n";

export default async function Layout({
  params,
  children,
}: {
  params: Promise<{ lang: string }>;
  children: ReactNode;
}) {
  const { lang } = await params;
  const { t } = useI18n(lang as Locale);
  const options = baseOptions(lang, t);
  return (
    <DocsLayout
      {...options}
      nav={{
        ...options.nav,
        mode: "top",
      }}
      links={[]}
      tabMode="navbar"
      tree={source.getPageTree(lang)}
    >
      {children}
    </DocsLayout>
  );
}

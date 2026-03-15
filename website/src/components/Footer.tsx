"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useI18n } from "@/hooks/useI18n";
import type { Locale } from "@/i18n";

const Footer = () => {
  const { lang } = useParams();
  const { t } = useI18n(lang as Locale);

  const footerLinks = [
    {
      category: t("Footer.store.title"),
      links: [
        {
          name: t("Footer.store.toolStore"),
          href: "https://store.tgo.ai/store",
          target: "_blank",
        },
        {
          name: t("Footer.store.modelMarket"),
          href: "https://store.tgo.ai/models",
          target: "_blank",
        },
      ],
    },
    {
      category: t("Footer.resources.title"),
      links: [
        { name: t("Footer.resources.docs"), href: `/${lang}/docs`, target: "" },
        {
          name: t("Footer.resources.contact"),
          href: "https://github.com/tgoai/tgo/issues",
          target: "_blank",
        },
      ],
    },
  ];

  return (
    <footer className="bg-gray-900 text-white">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-8">
          <div className="lg:col-span-1">
            <div className="flex items-center space-x-2 mb-4">
              <img src="/logo.svg" alt="Tgo" className="w-8 h-8 rounded-lg" />
              <span className="text-xl font-bold">{t("Footer.title")}</span>
            </div>
            <p className="text-gray-400 text-sm mb-4">
              {t("Footer.description")}
            </p>
          </div>

          {footerLinks.map(({ category, links }) => (
            <div key={category}>
              <h3 className="text-lg font-semibold mb-4">{category}</h3>
              <ul className="space-y-2">
                {links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      target={link.target}
                      className="text-gray-400 hover:text-white text-sm transition-colors"
                    >
                      {link.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="border-t border-gray-800 mt-8 pt-8 flex flex-col md:flex-row justify-between items-center">
          <p className="text-gray-400 text-sm">{t("Footer.copyright")}</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;

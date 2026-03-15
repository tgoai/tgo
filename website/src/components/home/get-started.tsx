"use client";

import { FileText, Github, Mail } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useI18n } from "@/hooks/useI18n";
import type { Locale } from "@/i18n";

export function GetStarted() {
  const { lang } = useParams();
  const { t } = useI18n(lang as Locale);
  return (
    <section className="py-20 px-4 bg-linear-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-950">
      <div className="container mx-auto max-w-[1400px]">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            {t("GetStarted.heading")}
          </h2>
          <p className="text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
            {t("GetStarted.subheading")}
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <Link
            href={`/${lang}/docs`}
            className="flex flex-col items-center bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm hover:shadow-md transition-shadow text-center"
          >
            <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg mb-4">
              <FileText className="h-6 w-6 text-blue-600 dark:text-blue-400" />
            </div>
            <h3 className="text-xl font-semibold mb-2">
              {t("GetStarted.cards.docs.title")}
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              {t("GetStarted.cards.docs.description")}
            </p>
          </Link>

          <a
            href="https://github.com/tgoai/tgo"
            target="_blank"
            className="flex flex-col items-center bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm hover:shadow-md transition-shadow text-center"
            rel="noopener"
          >
            <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg mb-4">
              <Github className="h-6 w-6 text-blue-600 dark:text-blue-400" />
            </div>
            <h3 className="text-xl font-semibold mb-2">
              {t("GetStarted.cards.github.title")}
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              {t("GetStarted.cards.github.description")}
            </p>
          </a>

          <a
            href="https://github.com/tgoai/tgo/issues"
            target="_blank"
            className="flex flex-col items-center bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm hover:shadow-md transition-shadow text-center"
            rel="noopener"
          >
            <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg mb-4">
              <Mail className="h-6 w-6 text-blue-600 dark:text-blue-400" />
            </div>
            <h3 className="text-xl font-semibold mb-2">
              {t("GetStarted.cards.contact.title")}
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              {t("GetStarted.cards.contact.description")}
            </p>
          </a>
        </div>
      </div>
    </section>
  );
}

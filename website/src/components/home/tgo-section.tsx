"use client";

import Link from "next/link";
import { ArrowRight, BookOpenIcon } from "lucide-react";
import Image from "next/image";
import { useParams } from "next/navigation";
import { useI18n } from "@/hooks/useI18n";
import type { Locale } from "@/i18n";

export function TgoSection() {
  const { lang } = useParams();
  const { t } = useI18n(lang as Locale);

  return (
    <section className="py-20 px-4">
      <div className="container mx-auto my-20 max-w-[1400px]">
        <div className="flex flex-col items-center text-center">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 bg-clip-text text-transparent bg-linear-to-r from-blue-600 to-cyan-500">
            {t("TgoSection.title")}
          </h1>
          <p className="text-xl md:text-2xl leading-relaxed text-balance max-w-6xl mb-10 text-gray-700 dark:text-gray-300">
            {t("TgoSection.descriptionLine1")}
            <br />
            {t("TgoSection.descriptionLine2")}
          </p>

          <div className="flex flex-col sm:flex-row gap-4">
            <a
              href={`/${lang}/docs/quick-start/deploy`}
              className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg transition-colors"
            >
              {t("TgoSection.buttons.getStarted")}
              <ArrowRight size={18} />
            </a>
            <Link
              href={`/${lang}/docs`}
              className="flex items-center justify-center gap-2 bg-gray-200 dark:bg-gray-800 hover:bg-gray-300 dark:hover:bg-gray-700 px-6 py-3 rounded-lg transition-colors"
            >
              {t("TgoSection.buttons.readDocs")}
              <BookOpenIcon size={18} />
            </Link>
          </div>
        </div>

        <div className="mt-16 relative">
          <div className="absolute rounded-2xl inset-0 bg-linear-to-t via-60% from-white dark:from-gray-950 z-10 top-64 bottom-0"></div>
          <div className="bg-gray-100 dark:bg-gray-800 rounded-2xl p-4 md:p-4 shadow-lg">
            <div className="aspect-16/10 rounded-lg flex items-center justify-center">
              <Image
                width={2940}
                height={1840}
                src={`/${lang}/home.png`}
                alt="Tgo Hero Image"
                className="rounded-lg w-full hidden dark:block"
              />
              <Image
                width={2940}
                height={1840}
                src={`/${lang}/home.png`}
                alt="Tgo Hero Image"
                className="rounded-lg w-full block dark:hidden"
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

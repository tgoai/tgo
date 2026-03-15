import { type Locale, translations } from "@/i18n";

export function useI18n(locale: Locale) {
  return {
    t: (key: string, params?: Record<string, string | number>) => {
      const keys = key.split(".");
      let value: unknown = translations[locale];

      for (const k of keys) {
        if (value && typeof value === "object" && k in value) {
          value = (value as Record<string, unknown>)[k];
        } else {
          return key;
        }
      }

      let result = typeof value === "string" ? value : key;

      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          result = result.replace(
            new RegExp(`\\{\\{${k}\\}\\}`, "g"),
            String(v),
          );
        });
      }

      return result;
    },
    ta: <T = unknown>(key: string): T => {
      const keys = key.split(".");
      let value: unknown = translations[locale];

      for (const k of keys) {
        if (value && typeof value === "object" && k in value) {
          value = (value as Record<string, unknown>)[k];
        } else {
          return key as T;
        }
      }

      return value as T;
    },
  };
}

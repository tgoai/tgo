import zh from "./locales/zh.json";
import en from "./locales/en.json";

export type Locale = "zh" | "en";

export type TranslationKeys = typeof zh | typeof en;

export const translations: Record<Locale, typeof zh> = { zh, en };

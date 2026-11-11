export type Locale = "en" | "zh-CN";
export type Catalog = Record<string, string>;
export const preferenceKey = "engine.site.locale.v1";
export function translate(
  catalog: Catalog,
  english: Catalog,
  key: string,
): string {
  return catalog[key] ?? english[key] ?? key;
}
export function savedLocale(
  storage: Pick<Storage, "getItem"> | undefined,
): Locale {
  try {
    return storage?.getItem(preferenceKey) === "zh-CN" ? "zh-CN" : "en";
  } catch {
    return "en";
  }
}
export function persistLocale(
  storage: Pick<Storage, "setItem"> | undefined,
  locale: Locale,
) {
  try {
    storage?.setItem(preferenceKey, locale);
  } catch {
    /* Preference cannot block document navigation. */
  }
}
export function pairedRoute(
  path: string,
  locale: Locale,
  pairs: Record<string, string>,
): string {
  for (const [en, zh] of Object.entries(pairs)) {
    if (path === en || path === zh) return locale === "zh-CN" ? zh : en;
  }
  return path;
}

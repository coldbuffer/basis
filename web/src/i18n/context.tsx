import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { getStoredLocale, setStoredLocale } from '@/i18n/preferences.js';
import { LOCALE_HTML_LANG, type Locale } from './locale.js';
import { en, type LocaleMessages } from './en.js';
import { zh } from './zh.js';

export type { Locale };

const locales: Record<Locale, LocaleMessages> = { en, zh: zh as unknown as LocaleMessages };

const I18nContext = createContext<{
  locale: Locale;
  t: LocaleMessages;
  setLocale: (locale: Locale) => void;
}>({ locale: 'zh', t: locales.zh, setLocale: () => {} });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => getStoredLocale());
  const t = useMemo(() => locales[locale], [locale]);

  const handleSetLocale = useCallback((next: Locale) => {
    setLocale(next);
    setStoredLocale(next);
  }, []);

  useEffect(() => {
    document.documentElement.lang = LOCALE_HTML_LANG[locale];
  }, [locale]);

  return (
    <I18nContext.Provider value={{ locale, t, setLocale: handleSetLocale }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}

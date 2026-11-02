import { isLocale, type Locale, localeFromBrowser } from './locale.js';

const LOCALE_KEY = 'fellow:locale';

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore quota / private mode */
  }
}

export function getSystemLocale(): Locale {
  if (typeof navigator === 'undefined') return 'zh';
  const lang = navigator.language || navigator.languages?.[0] || '';
  return localeFromBrowser(lang);
}

export function getStoredLocale(): Locale {
  const value = readStorage(LOCALE_KEY);
  return value && isLocale(value) ? value : getSystemLocale();
}

export function setStoredLocale(locale: Locale) {
  writeStorage(LOCALE_KEY, locale);
}

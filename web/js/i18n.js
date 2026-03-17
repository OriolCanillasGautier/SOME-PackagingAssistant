const STORAGE_KEY = 'packassist-language';
const DEFAULT_LANGUAGE = 'ca';
const localeCache = new Map();

function resolveLocaleUrl(language) {
    return new URL(`../locales/${language}.json`, import.meta.url);
}

export function getStoredLanguage() {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored || document.documentElement.lang || DEFAULT_LANGUAGE;
}

export function setStoredLanguage(language) {
    localStorage.setItem(STORAGE_KEY, language);
}

export function getLocaleCode(language) {
    return language === 'ca' ? 'ca-ES' : 'en-US';
}

export async function loadLocale(language = DEFAULT_LANGUAGE) {
    const normalized = language || DEFAULT_LANGUAGE;
    if (localeCache.has(normalized)) {
        return localeCache.get(normalized);
    }

    let response = await fetch(resolveLocaleUrl(normalized));
    if (!response.ok && normalized !== DEFAULT_LANGUAGE) {
        response = await fetch(resolveLocaleUrl(DEFAULT_LANGUAGE));
    }
    if (!response.ok) {
        throw new Error(`Unable to load locale: ${normalized}`);
    }

    const locale = await response.json();
    localeCache.set(normalized, locale);
    return locale;
}

export function getText(locale, path, fallback = path) {
    const value = path.split('.').reduce((acc, key) => acc && acc[key], locale);
    return value == null ? fallback : value;
}

export function interpolate(template, variables = {}) {
    return String(template).replace(/\{(\w+)\}/g, (_, key) => {
        const value = variables[key];
        return value == null ? `{${key}}` : String(value);
    });
}

export function t(locale, path, variables = {}, fallback = path) {
    const value = getText(locale, path, fallback);
    if (typeof value !== 'string') return value;
    return interpolate(value, variables);
}

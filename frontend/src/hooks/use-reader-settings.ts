"use client";

import { useState, useCallback, useEffect } from "react";

interface ReaderSettings {
  arabicFontSize: number;
  englishFontSize: number;
  theme: "light" | "dark" | "sepia";
}

const DEFAULTS: ReaderSettings = {
  arabicFontSize: 1.5,
  englishFontSize: 1,
  theme: "light",
};

const STORAGE_KEY = "ilm-atlas-reader-settings";
const STEP = 0.125;
const MIN_SIZE = 0.75;
const MAX_SIZE = 3;

function load(): ReaderSettings {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return DEFAULTS;
  }
}

function save(settings: ReaderSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function useReaderSettings() {
  const [settings, setSettings] = useState<ReaderSettings>(DEFAULTS);

  useEffect(() => {
    setSettings(load());
  }, []);

  const update = useCallback((partial: Partial<ReaderSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...partial };
      save(next);
      return next;
    });
  }, []);

  const increaseArabic = useCallback(() => {
    update({ arabicFontSize: Math.min(settings.arabicFontSize + STEP, MAX_SIZE) });
  }, [settings.arabicFontSize, update]);

  const decreaseArabic = useCallback(() => {
    update({ arabicFontSize: Math.max(settings.arabicFontSize - STEP, MIN_SIZE) });
  }, [settings.arabicFontSize, update]);

  const increaseEnglish = useCallback(() => {
    update({ englishFontSize: Math.min(settings.englishFontSize + STEP, MAX_SIZE) });
  }, [settings.englishFontSize, update]);

  const decreaseEnglish = useCallback(() => {
    update({ englishFontSize: Math.max(settings.englishFontSize - STEP, MIN_SIZE) });
  }, [settings.englishFontSize, update]);

  return {
    settings,
    update,
    increaseArabic,
    decreaseArabic,
    increaseEnglish,
    decreaseEnglish,
  };
}

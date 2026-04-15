import { describe, expect, it } from "vitest";

import { getTranslations } from "@/lib/i18n";
import {
  localizeGeoLinguisticReason,
  localizeLanguageFlagReason,
  localizePlaintextLanguageSummary,
} from "@/components/preview-modal/reason-localization";

const mixContext = {
  serving_countries: ["IN"],
  primary_text_language: "English",
  primary_text_language_code: "en",
  secondary_text_language: "Spanish",
  secondary_text_language_code: "es",
  secondary_text_sample: "instalar",
};

describe("preview modal reason localization", () => {
  it("localizes deterministic CTA mix reasons in Chinese", () => {
    expect(
      localizeLanguageFlagReason(
        "zh",
        getTranslations("zh").previewModal,
        "Spanish CTA 'instalar' mixed into English creative serving in IND",
        mixContext,
      ),
    ).toBe("在印度投放的英语素材中混入了西班牙语 CTA“instalar”");
  });

  it("localizes plaintext CTA summaries in Chinese", () => {
    expect(
      localizePlaintextLanguageSummary(
        "zh",
        getTranslations("zh").previewModal,
        "Primary plaintext: English · CTA: Spanish ('instalar')",
        mixContext,
      ),
    ).toBe("主要正文：英语 · CTA：西班牙语（“instalar”）");
  });

  it("localizes AI language-mix reasons in Chinese", () => {
    expect(
      localizeGeoLinguisticReason(
        "zh",
        getTranslations("zh").previewModal,
        "Spanish word 'instalar' (install) mixed with English primary content served in India",
        mixContext,
      ),
    ).toBe("在印度投放的以英语为主的内容中混入了西班牙语词语“instalar”");
  });

  it("localizes AI language-mix reasons in Hebrew", () => {
    expect(
      localizeGeoLinguisticReason(
        "he",
        getTranslations("he").previewModal,
        "Spanish word 'instalar' (install) mixed with English primary content served in India",
        mixContext,
      ),
    ).toBe('המילה "instalar" בשפה ספרדית משולבת בתוכן שעיקרו אנגלית ומוצג בהודו');
  });

  it("localizes the supported non-English locales away from the raw English string", () => {
    const rawReason =
      "Spanish word 'instalar' (install) mixed with English primary content served in India";

    for (const locale of ["es", "pl", "zh", "ru", "uk", "da", "fr", "nl", "he", "ar"] as const) {
      const localized = localizeGeoLinguisticReason(
        locale,
        getTranslations(locale).previewModal,
        rawReason,
        mixContext,
      );

      expect(localized).not.toBe(rawReason);
      expect(localized).toContain("instalar");
    }
  });

  it("keeps English copy unchanged outside Chinese locale", () => {
    expect(
      localizeGeoLinguisticReason(
        "en",
        getTranslations("en").previewModal,
        "Spanish word 'instalar' (install) mixed with English primary content served in India",
        mixContext,
      ),
    ).toBe(
      "Spanish word 'instalar' (install) mixed with English primary content served in India",
    );
  });
});

import { describe, expect, it } from "vitest";

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
        "Spanish CTA 'instalar' mixed into English creative serving in IND",
        mixContext,
      ),
    ).toBe("在印度投放的英语素材中混入了西班牙语 CTA“instalar”");
  });

  it("localizes plaintext CTA summaries in Chinese", () => {
    expect(
      localizePlaintextLanguageSummary(
        "zh",
        "Primary plaintext: English · CTA: Spanish ('instalar')",
        mixContext,
      ),
    ).toBe("主要正文：英语 · CTA：西班牙语（“instalar”）");
  });

  it("localizes AI language-mix reasons in Chinese", () => {
    expect(
      localizeGeoLinguisticReason(
        "zh",
        "Spanish word 'instalar' (install) mixed with English primary content served in India",
        mixContext,
      ),
    ).toBe("在印度投放的以英语为主的内容中混入了西班牙语词语“instalar”");
  });

  it("keeps English copy unchanged outside Chinese locale", () => {
    expect(
      localizeGeoLinguisticReason(
        "en",
        "Spanish word 'instalar' (install) mixed with English primary content served in India",
        mixContext,
      ),
    ).toBe(
      "Spanish word 'instalar' (install) mixed with English primary content served in India",
    );
  });
});

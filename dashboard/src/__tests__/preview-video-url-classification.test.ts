import { describe, expect, it } from "vitest";

import {
  looksLikeDirectVideoUrl,
  looksLikeVastUrl,
} from "@/components/preview-modal/PreviewRenderers";

describe("video preview URL classification", () => {
  it("does not treat VAST tag URLs as direct video media", () => {
    const vastUrl =
      "https://vast.ochanges.com/vast?creative_id=1226&placement_type=video";

    expect(looksLikeVastUrl(vastUrl)).toBe(true);
    expect(looksLikeDirectVideoUrl(vastUrl)).toBe(false);
  });

  it("recognizes direct video assets with query strings", () => {
    const mediaUrl = "https://cdn.example.com/creative/video.mp4?token=abc";

    expect(looksLikeDirectVideoUrl(mediaUrl)).toBe(true);
    expect(looksLikeVastUrl(mediaUrl)).toBe(false);
  });
});

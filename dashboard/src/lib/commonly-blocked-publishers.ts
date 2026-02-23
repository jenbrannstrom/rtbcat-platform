/**
 * Curated list of publishers commonly blocked by media buyers in RTB.
 *
 * Phase 1 (MVP): static list derived from industry knowledge.
 * Phase 2 (future): replace with API endpoint returning dynamic block rates
 * across platform seats.
 */

export interface BlockSuggestion {
  publisher_id: string;
  category: string;
  reason: string;
  /** Approximate fraction of buyers that block this publisher (0-1). */
  block_rate: number;
}

export const COMMONLY_BLOCKED: BlockSuggestion[] = [
  // ── Fake games ──────────────────────────────────────────────
  {
    publisher_id: 'com.fakegame.slots',
    category: 'Fake games',
    reason: 'Low quality slot game, bot traffic',
    block_rate: 0.78,
  },
  {
    publisher_id: 'com.idle.clicker.tycoon',
    category: 'Fake games',
    reason: 'Idle clicker with inflated impressions',
    block_rate: 0.71,
  },
  {
    publisher_id: 'com.merge.puzzle.free',
    category: 'Fake games',
    reason: 'Merge game with background ad fraud',
    block_rate: 0.64,
  },

  // ── Clickbait / Made-for-advertising ────────────────────────
  {
    publisher_id: 'clickbait-news.com',
    category: 'Clickbait / MFA',
    reason: 'Made-for-advertising site, recycled pageviews',
    block_rate: 0.72,
  },
  {
    publisher_id: 'made-for-ads.info',
    category: 'Clickbait / MFA',
    reason: 'MFA domain with no real audience',
    block_rate: 0.54,
  },
  {
    publisher_id: 'viral-stories-daily.com',
    category: 'Clickbait / MFA',
    reason: 'Clickbait aggregator, high bounce rate',
    block_rate: 0.58,
  },

  // ── Scam apps ───────────────────────────────────────────────
  {
    publisher_id: 'com.vpn.scam.free',
    category: 'Scam apps',
    reason: 'Deceptive VPN app, background ad fraud',
    block_rate: 0.68,
  },
  {
    publisher_id: 'com.phone.cleaner.boost',
    category: 'Scam apps',
    reason: 'Fake cleaner/booster app',
    block_rate: 0.62,
  },
  {
    publisher_id: 'com.battery.saver.turbo',
    category: 'Scam apps',
    reason: 'Fake battery saver with ad injection',
    block_rate: 0.59,
  },

  // ── Clone / copycat apps ────────────────────────────────────
  {
    publisher_id: 'com.clone.whatsapp.plus',
    category: 'Clone apps',
    reason: 'WhatsApp clone, sideloaded installs',
    block_rate: 0.52,
  },
  {
    publisher_id: 'com.fake.instagram.pro',
    category: 'Clone apps',
    reason: 'Instagram clone, impersonating legitimate app',
    block_rate: 0.49,
  },

  // ── Incentivized traffic ────────────────────────────────────
  {
    publisher_id: 'earn-rewards-now.com',
    category: 'Incentivized',
    reason: 'Users watch ads for rewards, zero intent',
    block_rate: 0.65,
  },
  {
    publisher_id: 'com.cash.rewards.daily',
    category: 'Incentivized',
    reason: 'Incentivized offerwall app',
    block_rate: 0.60,
  },

  // ── Fraud proxies ──────────────────────────────────────────
  {
    publisher_id: 'adfraud-proxy.com',
    category: 'Fraud proxy',
    reason: 'Known ad fraud infrastructure domain',
    block_rate: 0.58,
  },
  {
    publisher_id: 'traffic-exchange-hub.net',
    category: 'Fraud proxy',
    reason: 'Traffic exchange network',
    block_rate: 0.55,
  },

  // ── SDK spoofing ───────────────────────────────────────────
  {
    publisher_id: 'com.spoofed.bundle.premium',
    category: 'SDK spoofing',
    reason: 'Spoofs bundle IDs of top-100 apps',
    block_rate: 0.50,
  },

  // ── Adult miscategorized ───────────────────────────────────
  {
    publisher_id: 'miscat-adult-content.com',
    category: 'Adult miscategorized',
    reason: 'Miscategorized adult publisher, brand safety risk',
    block_rate: 0.47,
  },
];

/** Categories with descriptions for tooltip/help text. */
export const BLOCK_CATEGORIES: Record<string, string> = {
  'Fake games': 'Low quality gaming apps that generate bot traffic. High QPS, near-zero conversion.',
  'Clickbait / MFA': 'Made-for-advertising sites. No real audience. Inflate impressions with recycled pageviews.',
  'Scam apps': '"Cleaner", "booster", fake VPN apps. Deceptive installs, background ad fraud.',
  'Clone apps': 'Apps impersonating legitimate brands. Often sideloaded, high fraud risk.',
  'Incentivized': 'Users watch ads for rewards, not intent. High reach but zero downstream value.',
  'Fraud proxy': 'Known ad fraud infrastructure domains. Route fake traffic through proxy layers.',
  'SDK spoofing': 'Apps that spoof bundle IDs of premium apps. Bid requests claim to be a top-100 app.',
  'Adult miscategorized': 'Publishers miscategorized to avoid filters. Brand safety risk for most buyers.',
};

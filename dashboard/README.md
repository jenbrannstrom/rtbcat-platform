# RTB.cat Dashboard

Next.js dashboard for visualizing creatives and RTB waste analysis.

## Overview

The dashboard provides a unified interface for:
- Viewing and filtering creatives from Google Authorized Buyers
- Analyzing RTB waste patterns from CAT_SCAN
- Live metrics and performance insights

## Tech Stack

- **Framework**: Next.js 16 with App Router
- **UI**: React 19, Tailwind CSS
- **Data Fetching**: TanStack React Query
- **Charts**: Recharts
- **Icons**: Lucide React

## Quick Start

### Prerequisites
- Node.js 18+
- npm or yarn

### Development
```bash
cd dashboard

# Install dependencies
npm install

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build
```bash
npm run build
npm run start
```

### Docker
```bash
docker build -t rtbcat-dashboard .
docker run -p 3000:3000 rtbcat-dashboard
```

## Project Structure

```
dashboard/
├── src/
│   ├── app/                 # Next.js App Router pages
│   │   ├── campaigns/       # Campaign management
│   │   ├── collect/         # Data collection triggers
│   │   ├── creatives/       # Creative browser
│   │   ├── settings/        # Configuration
│   │   ├── layout.tsx       # Root layout
│   │   ├── page.tsx         # Home page
│   │   └── providers.tsx    # React Query provider
│   ├── components/          # Reusable components
│   │   ├── creative-card.tsx
│   │   ├── format-chart.tsx
│   │   ├── preview-modal.tsx
│   │   ├── sidebar.tsx
│   │   └── stats-card.tsx
│   ├── lib/                 # Utilities
│   └── types/               # TypeScript types
├── public/                  # Static assets
├── tailwind.config.ts
└── package.json
```

## Pages

### Home (`/`)
Overview dashboard with key metrics:
- Total creatives count
- Format distribution chart
- Recent activity

### Creatives (`/creatives`)
Browse and filter creatives:
- Filter by format (HTML, VIDEO, NATIVE)
- Filter by size category (IAB Standard, Video, Adaptive)
- Filter by canonical size (300x250, 728x90, etc.)
- Search by advertiser name
- Preview creative content

### Campaigns (`/campaigns`)
View grouped creatives by campaign:
- UTM-based campaign grouping
- AI-powered clustering
- Performance metrics per campaign

### Collect (`/collect`)
Trigger data collection:
- Manual sync from Authorized Buyers API
- View collection status
- Schedule automatic syncs

### Settings (`/settings`)
Configure dashboard:
- API credentials
- Refresh intervals
- Display preferences

## Components

### CreativeCard
Displays a single creative with:
- Thumbnail preview
- Size information
- Format badge
- Quick actions

### FormatChart
Pie/bar chart showing:
- Format distribution
- Size category breakdown

### PreviewModal
Full creative preview:
- HTML rendering (sandboxed)
- Video playback
- Native ad components

### StatsCard
Metric display with:
- Current value
- Trend indicator
- Comparison to previous period

## API Integration

The dashboard connects to the Creative Intelligence API:

```typescript
// Example: Fetch creatives
const response = await fetch('http://localhost:8000/api/creatives', {
  params: {
    format: 'HTML',
    size_category: 'IAB Standard',
    limit: 100
  }
});
```

### Endpoints Used

| Endpoint | Description |
|----------|-------------|
| `GET /api/creatives` | List creatives with filters |
| `GET /api/creatives/{id}` | Get single creative |
| `GET /api/stats` | Get aggregate statistics |
| `GET /api/campaigns` | List campaigns |
| `POST /api/collect` | Trigger data collection |

## Environment Variables

Create `.env.local`:

```bash
# Creative Intelligence API
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional: Analytics
NEXT_PUBLIC_ANALYTICS_ID=
```

## Styling

Uses Tailwind CSS with custom configuration:

```typescript
// tailwind.config.ts
module.exports = {
  theme: {
    extend: {
      colors: {
        // Custom brand colors
      }
    }
  }
}
```

## Development

### Linting
```bash
npm run lint
```

### Type Checking
```bash
npx tsc --noEmit
```

### Adding New Pages

1. Create folder in `src/app/`
2. Add `page.tsx` for the route
3. Add to sidebar navigation in `src/components/sidebar.tsx`

## Related Documentation

- [Creative Intelligence API](../creative-intelligence/README.md)
- [CAT_SCAN Analyzer](../cat-scan/README.md)

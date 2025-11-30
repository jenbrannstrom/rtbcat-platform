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

### Waste Analysis (`/waste-analysis`)
RTB waste analysis dashboard:
- Size gap analysis with recommendations
- Traffic pattern visualization (daily QPS)
- Size coverage heatmap
- Actionable recommendations (block, add creative, use flexible)
- Potential savings calculations

### Creatives (`/creatives`)
Browse and filter creatives:
- Filter by format (HTML, VIDEO, NATIVE)
- Filter by size category (IAB Standard, Video, Adaptive)
- Filter by canonical size (300x250, 728x90, etc.)
- Search by advertiser name
- Preview creative content
- Performance metrics on cards (spend, CTR, CPM, CPC)
- Seat name display (instead of raw IDs)

### Campaigns (`/campaigns`)
View grouped creatives by campaign:
- UTM-based campaign grouping
- AI-powered clustering with auto-cluster button
- Performance metrics per campaign
- Daily trend charts
- Campaign management (rename, delete)

### Collect (`/collect`)
Trigger data collection:
- Manual sync from Authorized Buyers API
- View collection status
- Per-seat sync option

### Import (`/import`)
Import performance data:
- CSV file upload for performance metrics
- Support for impressions, clicks, spend
- Progress indicator during import
- Validation and error reporting

### Settings (`/settings`)
Configure dashboard:
- API status and health check
- Database statistics
- Links to sub-settings pages

### Settings > Seats (`/settings/seats`)
Manage buyer seats:
- View all buyer seats with creative counts
- Rename seats with inline editing
- Last synced timestamps
- Link to view creatives per seat
- Populate from existing creatives button

### Settings > Retention (`/settings/retention`)
Data retention configuration:
- Configure retention periods
- Cleanup schedules

## Components

### Sidebar
Left navigation with:
- Collapsible design (persisted to localStorage)
- Seat selector dropdown with creative counts
- Quick sync button for selected seat
- Navigation links (Dashboard, Waste Analysis, Creatives, Campaigns, Collect, Import, Settings)

### CreativeCard
Displays a single creative with:
- Thumbnail preview (video, native image, HTML placeholder)
- Size information and format badge
- Performance metrics (spend, CTR, CPM, CPC) when available
- Seat name display (instead of raw account IDs)
- Google Authorized Buyers link
- Preview button

### FormatChart
Pie/bar chart showing:
- Format distribution
- Size category breakdown

### PreviewModal
Full creative preview:
- HTML rendering (sandboxed iframe)
- Video playback with VAST XML support
- Native ad components (headline, body, image, logo)
- Copy creative ID button

### StatsCard
Metric display with:
- Current value
- Trend indicator
- Comparison to previous period

### SeatSelector
Dropdown for selecting buyer seats:
- Shows all available seats
- Creative count per seat
- Last synced timestamp
- "All Seats" option

## Known Issues

1. **Seat dropdown shows 0 creatives**: Run `/seats/populate` API endpoint after importing creatives
2. **Hot reload not updating**: Sometimes requires `npm run build` after backend changes
3. **Performance metrics not showing**: Import CSV performance data via `/import` page first
4. **HTML/Video card thumbnails**: Currently show placeholder icons; full preview available in modal

## Roadmap

### Phase 10: Thumbnail Generation (Planned)

Generate offline thumbnails for faster card previews:

**HTML Creatives:**
- Use Playwright/Puppeteer to render HTML and screenshot
- Store thumbnails locally or in S3

**Video Creatives:**
- Use ffmpeg to extract frame at 1 second
- Generate poster image for video cards

**Database Changes:**
```sql
ALTER TABLE creatives ADD COLUMN thumbnail_url TEXT;
```

**Implementation:**
- Background job on creative sync/import
- Queue system (Celery or cron-based)
- Thumbnail storage: `~/.rtbcat/thumbnails/` or S3

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

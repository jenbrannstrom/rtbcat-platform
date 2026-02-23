import { ExternalLink } from "lucide-react";

/**
 * Instructions for creating 5 daily CSV reports in Google Authorized Buyers.
 * Based on DATA_MODEL.md specifications.
 */
export function ExportInstructions() {
  return (
    <div className="space-y-6 text-sm">
      {/* Why 5 Reports */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <h4 className="font-semibold text-amber-900 mb-2">Why 5 Separate Reports?</h4>
        <p className="text-amber-800 mb-2">
          Google Authorized Buyers has <strong>field incompatibilities</strong> that prevent getting all data in one export:
        </p>
        <ul className="text-amber-700 space-y-1 ml-4">
          <li>• To get Creative-level bid metrics, you lose &quot;Bid requests&quot;</li>
          <li>• To get &quot;Bid requests&quot;, you lose Creative detail</li>
          <li>• Pretargeting config (Billing ID) cannot be combined with bid pipeline metrics</li>
        </ul>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-2">Create 5 Scheduled Reports in Authorized Buyers</h4>
        <ol className="list-decimal list-inside text-gray-700 space-y-1">
          <li>Open <a href="https://authorized-buyers.google.com/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline inline-flex items-center gap-1">Authorized Buyers <ExternalLink className="h-3 w-3" /></a></li>
          <li>Go to <strong>Reporting</strong> → <strong>Scheduled Reports</strong> → <strong>New Report</strong></li>
          <li>Create each report below with schedule: <strong>Daily</strong>, date range: <strong>Yesterday</strong>, format: <strong>CSV</strong></li>
        </ol>
      </div>

      {/* Report 1: Bids in Auction */}
      <div className="border-2 border-blue-200 rounded-lg p-4 bg-blue-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-blue-600 text-white text-xs font-bold px-2 py-1 rounded">1</span>
          <h4 className="font-semibold text-gray-900">catscan-bidsinauction</h4>
          <span className="text-xs text-gray-500 ml-auto">→ rtb_daily</span>
        </div>
        <p className="text-gray-600 mb-3">Creative-level performance with bid pipeline metrics by country.</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Day</li>
              <li>• Country</li>
              <li>• Creative ID</li>
              <li>• Buyer account ID</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Bids in auction</li>
              <li>• Auctions won</li>
              <li>• Bids</li>
              <li>• Reached queries</li>
              <li>• Impressions</li>
              <li>• Spend (buyer currency)</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Report 2: Quality/Viewability */}
      <div className="border-2 border-purple-200 rounded-lg p-4 bg-purple-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-purple-600 text-white text-xs font-bold px-2 py-1 rounded">2</span>
          <h4 className="font-semibold text-gray-900">catscan-quality</h4>
          <span className="text-xs text-gray-500 ml-auto">→ rtb_daily</span>
        </div>
        <p className="text-gray-600 mb-3">Creative-level performance with viewability metrics. Includes pretargeting config (Billing ID) for config analysis.</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Day</li>
              <li>• Pretargeting config (Billing ID)</li>
              <li>• Creative ID</li>
              <li>• Creative size</li>
              <li>• Creative format</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Reached queries</li>
              <li>• Impressions</li>
              <li>• Spend (buyer currency)</li>
              <li>• Active view viewable</li>
              <li>• Active view measurable</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Report 3: Pipeline Geo */}
      <div className="border-2 border-green-200 rounded-lg p-4 bg-green-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-green-600 text-white text-xs font-bold px-2 py-1 rounded">3</span>
          <h4 className="font-semibold text-gray-900">catscan-pipeline-geo</h4>
          <span className="text-xs text-gray-500 ml-auto">→ rtb_bidstream</span>
        </div>
        <p className="text-gray-600 mb-3">Full bid pipeline by country and hour. Shows traffic volume you&apos;re receiving.</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Day</li>
              <li>• Country</li>
              <li>• Hour</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Bid requests</li>
              <li>• Inventory matches</li>
              <li>• Successful responses</li>
              <li>• Bids</li>
              <li>• Bids in auction</li>
              <li>• Auctions won</li>
              <li>• Impressions</li>
              <li>• Clicks</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Report 4: Pipeline Publishers */}
      <div className="border-2 border-orange-200 rounded-lg p-4 bg-orange-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-orange-600 text-white text-xs font-bold px-2 py-1 rounded">4</span>
          <h4 className="font-semibold text-gray-900">catscan-pipeline</h4>
          <span className="text-xs text-gray-500 ml-auto">→ rtb_bidstream</span>
        </div>
        <p className="text-gray-600 mb-3">Bid pipeline by publisher. Shows which publishers send you traffic.</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Day</li>
              <li>• Hour</li>
              <li>• Country</li>
              <li>• Publisher ID</li>
              <li>• Publisher name</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Bid requests</li>
              <li>• Inventory matches</li>
              <li>• Successful responses</li>
              <li>• Reached queries</li>
              <li>• Bids</li>
              <li>• Bids in auction</li>
              <li>• Auctions won</li>
              <li>• Impressions</li>
              <li>• Clicks</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Report 5: Bid Filtering */}
      <div className="border-2 border-red-200 rounded-lg p-4 bg-red-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-red-600 text-white text-xs font-bold px-2 py-1 rounded">5</span>
          <h4 className="font-semibold text-gray-900">catscan-bid-filtering</h4>
          <span className="text-xs text-gray-500 ml-auto">→ rtb_bid_filtering</span>
        </div>
        <p className="text-gray-600 mb-3">Understand why your bids are being filtered/rejected.</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Day</li>
              <li>• Country</li>
              <li>• Creative ID</li>
              <li>• Bid filtering reason</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Bids</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Naming Convention */}
      <div className="bg-gray-100 rounded-lg p-4">
        <h4 className="font-semibold text-gray-900 mb-2">Report Naming</h4>
        <p className="text-gray-700 mb-2">
          Name your reports: <code className="bg-white px-2 py-1 rounded border">catscan-{"{type}"}-{"{account_id}"}-yesterday-UTC</code>
        </p>
        <p className="text-gray-600 text-xs">
          Example: <code className="bg-white px-1 rounded">catscan-bidsinauction-1487810529-yesterday-UTC</code>
        </p>
      </div>

      <div className="bg-blue-50 p-3 rounded-lg">
        <p className="text-blue-800">
          <strong>Tip:</strong> Upload any CSV here. Cat-Scan <strong>automatically detects</strong> the report type
          from column headers and routes to the correct table.
        </p>
      </div>
    </div>
  );
}

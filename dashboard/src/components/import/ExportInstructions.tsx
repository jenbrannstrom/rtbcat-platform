import { ExternalLink } from "lucide-react";

/**
 * Instructions for exporting data from Google Authorized Buyers.
 * Explains the 3 required reports and 2 optional reports.
 */
export function ExportInstructions() {
  return (
    <div className="space-y-6 text-sm">
      {/* Why 3 Reports */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <h4 className="font-semibold text-amber-900 mb-2">Why 3 Separate Reports?</h4>
        <p className="text-amber-800 mb-2">
          Google Authorized Buyers has <strong>field incompatibilities</strong>:
        </p>
        <ul className="text-amber-700 space-y-1 ml-4">
          <li>• <code className="bg-amber-100 px-1 rounded">Mobile app ID</code> cannot be combined with <code className="bg-amber-100 px-1 rounded">Bid requests</code></li>
          <li>• <code className="bg-amber-100 px-1 rounded">Creative ID</code> cannot be combined with <code className="bg-amber-100 px-1 rounded">Bid requests</code></li>
        </ul>
        <p className="text-amber-800 mt-2">
          Cat-Scan joins these reports by <strong>Date + Country</strong> to give you the complete picture.
        </p>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-2">Go to Authorized Buyers Reporting</h4>
        <ol className="list-decimal list-inside text-gray-700 space-y-1">
          <li>Open <a href="https://authorized-buyers.google.com/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline inline-flex items-center gap-1">Authorized Buyers <ExternalLink className="h-3 w-3" /></a></li>
          <li>Navigate to <strong>Reporting</strong> → <strong>Scheduled Reports</strong> → <strong>New Report</strong></li>
        </ol>
      </div>

      {/* Report 1: Performance Detail */}
      <div className="border-2 border-blue-200 rounded-lg p-4 bg-blue-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-blue-600 text-white text-xs font-bold px-2 py-1 rounded">1</span>
          <span className="bg-blue-600 text-white text-xs font-bold px-2 py-1 rounded">Required</span>
          <h4 className="font-semibold text-gray-900">Performance Detail</h4>
          <span className="text-xs text-gray-500 ml-auto">→ rtb_daily table</span>
        </div>
        <p className="text-gray-600 mb-3">Creative, Size, and App-level performance. <strong>Has App/Creative detail but NO bid request metrics.</strong></p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions (in order)</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Day</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Billing ID</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Creative ID</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Creative size</strong></li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Creative format</li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Country</strong></li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Publisher ID</li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Mobile app ID</li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Mobile app name</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Reached queries</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Impressions</strong></li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Clicks</li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Spend (buyer currency)</li>
            </ul>
            <div className="mt-3 p-2 bg-red-100 rounded text-xs text-red-700">
              <strong>Cannot include:</strong> Bid requests, Bids, Bids in auction
            </div>
          </div>
        </div>
      </div>

      {/* Report 2: RTB Funnel (Geo) */}
      <div className="border-2 border-purple-200 rounded-lg p-4 bg-purple-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-purple-600 text-white text-xs font-bold px-2 py-1 rounded">2</span>
          <span className="bg-purple-600 text-white text-xs font-bold px-2 py-1 rounded">Required</span>
          <h4 className="font-semibold text-gray-900">RTB Funnel (Geo Only)</h4>
          <span className="text-xs text-gray-500 ml-auto">→ rtb_funnel table</span>
        </div>
        <p className="text-gray-600 mb-3">Full bid pipeline by country. <strong>Has Bid requests but NO Creative/App detail.</strong></p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions (in order)</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Day</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Country</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Buyer account ID</strong></li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Hour</li>
            </ul>
            <div className="mt-3 p-2 bg-red-100 rounded text-xs text-red-700">
              <strong>Cannot include:</strong> Creative ID, Creative size, Mobile app ID, Billing ID
            </div>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics (THE FUNNEL)</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-purple-600 font-bold">★</span> <strong>Bid requests</strong></li>
              <li className="flex items-center gap-2"><span className="text-purple-600 font-bold">★</span> <strong>Inventory matches</strong></li>
              <li className="flex items-center gap-2"><span className="text-purple-600 font-bold">★</span> <strong>Successful responses</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Reached queries</strong></li>
              <li className="flex items-center gap-2"><span className="text-purple-600 font-bold">★</span> <strong>Bids</strong></li>
              <li className="flex items-center gap-2"><span className="text-purple-600 font-bold">★</span> <strong>Bids in auction</strong></li>
              <li className="flex items-center gap-2"><span className="text-purple-600 font-bold">★</span> <strong>Auctions won</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Impressions</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Report 3: RTB Funnel (Publishers) */}
      <div className="border-2 border-green-200 rounded-lg p-4 bg-green-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-green-600 text-white text-xs font-bold px-2 py-1 rounded">3</span>
          <span className="bg-green-600 text-white text-xs font-bold px-2 py-1 rounded">Required</span>
          <h4 className="font-semibold text-gray-900">RTB Funnel (With Publishers)</h4>
          <span className="text-xs text-gray-500 ml-auto">→ rtb_funnel table</span>
        </div>
        <p className="text-gray-600 mb-3">Bid pipeline by publisher. <strong>Has Publisher + Bid requests but NO App detail.</strong></p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions (in order)</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Day</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Country</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Buyer account ID</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Publisher ID</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Publisher name</strong></li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Hour</li>
            </ul>
            <div className="mt-3 p-2 bg-red-100 rounded text-xs text-red-700">
              <strong>Cannot include:</strong> Creative ID, Mobile app ID
            </div>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics (same as Report 2)</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Bid requests</li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Inventory matches</li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Successful responses</li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Reached queries</li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Bids</li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Bids in auction</li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Auctions won</li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Impressions</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Report 4: Bid Filtering (Optional) */}
      <div className="border-2 border-orange-200 rounded-lg p-4 bg-orange-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-orange-600 text-white text-xs font-bold px-2 py-1 rounded">4</span>
          <span className="bg-gray-400 text-white text-xs font-bold px-2 py-1 rounded">Optional</span>
          <h4 className="font-semibold text-gray-900">Bid Filtering</h4>
          <span className="text-xs text-gray-500 ml-auto">→ rtb_bid_filtering table</span>
        </div>
        <p className="text-gray-600 mb-3">Understand <strong>why your bids are being filtered</strong>. Enables bid filtering analysis.</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Day</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Country</strong></li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Buyer account ID</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-orange-600 font-bold">★</span> <strong>Bid filtering reason</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Bids</li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Bids in auction</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Report 5: Quality Signals (Optional) */}
      <div className="border-2 border-red-200 rounded-lg p-4 bg-red-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-red-600 text-white text-xs font-bold px-2 py-1 rounded">5</span>
          <span className="bg-gray-400 text-white text-xs font-bold px-2 py-1 rounded">Optional</span>
          <h4 className="font-semibold text-gray-900">Quality Signals</h4>
          <span className="text-xs text-gray-500 ml-auto">→ rtb_quality table</span>
        </div>
        <p className="text-gray-600 mb-3">Fraud and viewability analysis. Enables <strong>IVT detection</strong> and viewability waste analysis.</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Day</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Publisher ID</strong></li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Publisher name</li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Country</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> Impressions</li>
              <li className="flex items-center gap-2"><span className="text-red-600 font-bold">★</span> <strong>IVT credited impressions</strong></li>
              <li className="flex items-center gap-2"><span className="text-red-600 font-bold">★</span> <strong>Pre-filtered impressions</strong></li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Active View measurable</li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Active View viewable</li>
            </ul>
          </div>
        </div>
      </div>

      {/* How Cat-Scan Joins */}
      <div className="bg-gray-100 rounded-lg p-4">
        <h4 className="font-semibold text-gray-900 mb-2">How Cat-Scan Joins the Data</h4>
        <div className="font-mono text-xs bg-white p-3 rounded border">
          <div className="text-purple-700">Report 2 (funnel-geo):</div>
          <div className="ml-4 text-gray-600">Bid requests → Bids → Auctions won (by country)</div>
          <div className="text-center my-1">↓ <span className="text-gray-400">JOIN ON date + country</span></div>
          <div className="text-blue-700">Report 1 (performance):</div>
          <div className="ml-4 text-gray-600">→ Creative breakdown, Size breakdown, App breakdown</div>
        </div>
        <p className="text-gray-600 text-xs mt-2">
          This gives AI the full picture: <strong>Total traffic → What you bid on → What you won → By which creative/app</strong>
        </p>
      </div>

      {/* Schedule Settings */}
      <div>
        <h4 className="font-semibold text-gray-900 mb-2">Schedule Settings (for all 3 reports)</h4>
        <ul className="list-disc list-inside text-gray-700 space-y-1">
          <li>Date range: <strong>Yesterday</strong></li>
          <li>Schedule: <strong>Daily</strong></li>
          <li>File format: <strong>CSV</strong></li>
        </ul>
      </div>

      <div className="bg-blue-50 p-3 rounded-lg">
        <p className="text-blue-800">
          <strong>Tip:</strong> Upload any CSV file here. Cat-Scan <strong>automatically detects</strong> all 5 report types
          from the column headers and routes to the correct table.
        </p>
      </div>
    </div>
  );
}

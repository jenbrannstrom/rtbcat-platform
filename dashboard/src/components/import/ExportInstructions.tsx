import { ExternalLink } from "lucide-react";
import { useTranslation } from "@/contexts/i18n-context";

/**
 * Instructions for creating 5 daily CSV reports in Google Authorized Buyers.
 * Based on DATA_MODEL.md specifications.
 */
export function ExportInstructions() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6 text-sm">
      {/* Why 5 Reports */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <h4 className="font-semibold text-amber-900 mb-2">{t.import.exportGuideWhyFiveReports}</h4>
        <p className="text-amber-800 mb-2">
          {t.import.exportGuideFieldIncompatibilities}
        </p>
        <ul className="text-amber-700 space-y-1 ml-4">
          <li>• {t.import.exportGuideLoseBidRequestsForCreativeMetrics}</li>
          <li>• {t.import.exportGuideLoseCreativeDetailForBidRequests}</li>
          <li>• {t.import.exportGuidePretargetingCannotCombine}</li>
        </ul>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-2">{t.import.exportGuideCreateFiveScheduledReports}</h4>
        <ol className="list-decimal list-inside text-gray-700 space-y-1">
          <li>
            {t.import.exportGuideStepOpen}{" "}
            <a href="https://authorized-buyers.google.com/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline inline-flex items-center gap-1">
              {t.import.exportGuideAuthorizedBuyersLabel} <ExternalLink className="h-3 w-3" />
            </a>
          </li>
          <li>{t.import.exportGuideStepReportingScheduledNewReport}</li>
          <li>{t.import.exportGuideStepCreateDailyYesterdayCsv}</li>
        </ol>
      </div>

      {/* Report 1: Bids in Auction */}
      <div className="border-2 border-blue-200 rounded-lg p-4 bg-blue-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-blue-600 text-white text-xs font-bold px-2 py-1 rounded">1</span>
          <h4 className="font-semibold text-gray-900">catscan-bidsinauction</h4>
          <span className="text-xs text-gray-500 ml-auto">→ rtb_daily</span>
        </div>
        <p className="text-gray-600 mb-3">{t.import.exportGuideReport1Desc}</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideDimensions}</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Day</li>
              <li>• Country</li>
              <li>• Creative ID</li>
              <li>• Buyer account ID</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideMetrics}</p>
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
        <p className="text-gray-600 mb-3">{t.import.exportGuideReport2Desc}</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideDimensions}</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Day</li>
              <li>• Pretargeting config (Billing ID)</li>
              <li>• Creative ID</li>
              <li>• Creative size</li>
              <li>• Creative format</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideMetrics}</p>
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
        <p className="text-gray-600 mb-3">{t.import.exportGuideReport3Desc}</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideDimensions}</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Day</li>
              <li>• Country</li>
              <li>• Hour</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideMetrics}</p>
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
        <p className="text-gray-600 mb-3">{t.import.exportGuideReport4Desc}</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideDimensions}</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Day</li>
              <li>• Hour</li>
              <li>• Country</li>
              <li>• Publisher ID</li>
              <li>• Publisher name</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideMetrics}</p>
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
        <p className="text-gray-600 mb-3">{t.import.exportGuideReport5Desc}</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideDimensions}</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Day</li>
              <li>• Country</li>
              <li>• Creative ID</li>
              <li>• Bid filtering reason</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideMetrics}</p>
            <ul className="space-y-1 text-gray-700">
              <li>• Bids</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Naming Convention */}
      <div className="bg-gray-100 rounded-lg p-4">
        <h4 className="font-semibold text-gray-900 mb-2">{t.import.exportGuideReportNaming}</h4>
        <p className="text-gray-700 mb-2">
          {t.import.exportGuideNameYourReports}{" "}
          <code className="bg-white px-2 py-1 rounded border">catscan-{"{type}"}-{"{account_id}"}-yesterday-UTC</code>
        </p>
        <p className="text-gray-600 text-xs">
          {t.import.exportGuideExampleLabel}{" "}
          <code className="bg-white px-1 rounded">catscan-bidsinauction-1487810529-yesterday-UTC</code>
        </p>
      </div>

      <div className="bg-blue-50 p-3 rounded-lg">
        <p className="text-blue-800">
          <strong>{t.import.exportGuideTipLabel}</strong>{" "}
          {t.import.exportGuideTipBody}
        </p>
      </div>
    </div>
  );
}

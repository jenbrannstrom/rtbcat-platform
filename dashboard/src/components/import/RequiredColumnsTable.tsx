/**
 * Information about required columns for each CSV report type.
 * Based on DATA_MODEL.md specifications.
 */
import { useTranslation } from "@/contexts/i18n-context";

export function RequiredColumnsTable() {
  const { t } = useTranslation();

  return (
    <div className="space-y-4 text-sm">
      <p className="text-gray-600">
        {t.import.requiredColumnsIntro}
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-100">
              <th className="p-2 border font-medium">{t.import.reportName}</th>
              <th className="p-2 border font-medium">{t.import.targetTable}</th>
              <th className="p-2 border font-medium">{t.import.requiredColumnsHeader}</th>
            </tr>
          </thead>
          <tbody className="text-xs">
            <tr>
              <td className="p-2 border font-medium text-blue-700">catscan-bidsinauction</td>
              <td className="p-2 border">rtb_daily</td>
              <td className="p-2 border">Day, Country, Creative ID, Buyer account ID, Bids in auction, Auctions won, Bids, Impressions</td>
            </tr>
            <tr className="bg-gray-50">
              <td className="p-2 border font-medium text-purple-700">catscan-quality</td>
              <td className="p-2 border">rtb_daily</td>
              <td className="p-2 border">Day, Pretargeting config (Billing ID), Creative ID, Creative size, Reached queries, Impressions, Active view viewable</td>
            </tr>
            <tr>
              <td className="p-2 border font-medium text-green-700">catscan-pipeline-geo</td>
              <td className="p-2 border">rtb_bidstream</td>
              <td className="p-2 border">Day, Country, Hour, Bid requests, Bids, Impressions</td>
            </tr>
            <tr className="bg-gray-50">
              <td className="p-2 border font-medium text-orange-700">catscan-pipeline</td>
              <td className="p-2 border">rtb_bidstream</td>
              <td className="p-2 border">Day, Country, Publisher ID, Publisher name, Bid requests, Bids, Impressions</td>
            </tr>
            <tr>
              <td className="p-2 border font-medium text-red-700">catscan-bid-filtering</td>
              <td className="p-2 border">rtb_bid_filtering</td>
              <td className="p-2 border">Day, Country, Creative ID, Bid filtering reason, Bids</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="bg-gray-50 p-3 rounded-lg">
        <p className="text-gray-700">
          <strong>{t.import.autoDetectionLogic}</strong>
        </p>
        <ul className="text-gray-600 mt-1 space-y-1 text-xs">
          <li>• Has <code className="bg-gray-200 px-1 rounded">Bid filtering reason</code>? → bid-filtering</li>
          <li>• Has <code className="bg-gray-200 px-1 rounded">Creative ID</code> + <code className="bg-gray-200 px-1 rounded">Bids in auction</code>? → bidsinauction</li>
          <li>• Has <code className="bg-gray-200 px-1 rounded">Creative ID</code> + <code className="bg-gray-200 px-1 rounded">Active view</code>? → quality</li>
          <li>• Has <code className="bg-gray-200 px-1 rounded">Bid requests</code> + <code className="bg-gray-200 px-1 rounded">Publisher ID</code>? → pipeline</li>
          <li>• Has <code className="bg-gray-200 px-1 rounded">Bid requests</code> only? → pipeline-geo</li>
        </ul>
      </div>
    </div>
  );
}

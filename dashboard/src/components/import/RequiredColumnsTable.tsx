/**
 * Information about required columns for CSV import.
 */
export function RequiredColumnsTable() {
  return (
    <div className="space-y-4 text-sm">
      <p className="text-gray-600">
        Cat-Scan imports <strong>all recognized columns</strong> from your CSV.
        Required columns depend on the report type.
      </p>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-2">
        <p className="text-blue-800 font-medium">Required columns by report</p>
        <ul className="text-blue-800 space-y-1">
          <li><strong>catscan-quality</strong>: Buyer account ID, Billing ID, Creative ID, Creative size, Day, Country, Reached queries, Impressions</li>
          <li><strong>catscan-bidsinauction</strong>: Buyer account ID, Country, Creative ID, Day, Hour, Bids in auction, Auctions won, Bids</li>
          <li><strong>catscan-rtb-pipeline</strong>: Buyer account ID, Country, Publisher ID, Day, Hour, Bid requests</li>
          <li><strong>catscan-pipeline-geo</strong>: Buyer account ID, Country, Day, Hour, Bid requests</li>
          <li><strong>catscan-bid-filtering</strong>: Buyer account ID, Country, Creative ID, Bid filtering reason, Day, Hour, Bids</li>
        </ul>
      </div>

      <div className="bg-gray-50 p-3 rounded-lg">
        <p className="text-gray-700">
          <strong>Column auto-detection:</strong> Cat-Scan automatically maps Google{"'"}s column names
          (e.g., <code className="bg-gray-200 px-1 rounded">#Creative ID</code> → <code className="bg-gray-200 px-1 rounded">creative_id</code>).
          Unknown columns are safely ignored.
        </p>
      </div>
    </div>
  );
}

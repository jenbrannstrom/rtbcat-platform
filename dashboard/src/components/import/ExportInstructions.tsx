import { ExternalLink } from "lucide-react";
import { useTranslation } from "@/contexts/i18n-context";

/**
 * Instructions for creating 5 daily CSV reports in Google Authorized Buyers.
 * Based on DATA_MODEL.md specifications.
 */
export function ExportInstructions() {
  const { t } = useTranslation();
  const reportCards = [
    {
      id: "1",
      containerClass: "border-2 border-blue-200 rounded-lg p-4 bg-blue-50",
      badgeClass: "bg-blue-600",
      reportName: t.import.requiredTableReportBidsInAuction,
      targetTable: t.import.targetTableRtbDaily,
      description: t.import.exportGuideReport1Desc,
      dimensions: [
        t.import.exportGuideDimDay,
        t.import.exportGuideDimCountry,
        t.import.exportGuideDimCreativeId,
        t.import.exportGuideDimBuyerAccountId,
      ],
      metrics: [
        t.import.exportGuideMetricBidsInAuction,
        t.import.exportGuideMetricAuctionsWon,
        t.import.exportGuideMetricBids,
        t.import.exportGuideMetricReachedQueries,
        t.import.exportGuideMetricImpressions,
        t.import.exportGuideMetricSpendBuyerCurrency,
      ],
    },
    {
      id: "2",
      containerClass: "border-2 border-purple-200 rounded-lg p-4 bg-purple-50",
      badgeClass: "bg-purple-600",
      reportName: t.import.requiredTableReportQuality,
      targetTable: t.import.targetTableRtbDaily,
      description: t.import.exportGuideReport2Desc,
      dimensions: [
        t.import.exportGuideDimDay,
        t.import.exportGuideDimPretargetingConfigBillingId,
        t.import.exportGuideDimCreativeId,
        t.import.exportGuideDimCreativeSize,
        t.import.exportGuideDimCreativeFormat,
      ],
      metrics: [
        t.import.exportGuideMetricReachedQueries,
        t.import.exportGuideMetricImpressions,
        t.import.exportGuideMetricSpendBuyerCurrency,
        t.import.exportGuideMetricActiveViewViewable,
        t.import.exportGuideMetricActiveViewMeasurable,
      ],
    },
    {
      id: "3",
      containerClass: "border-2 border-green-200 rounded-lg p-4 bg-green-50",
      badgeClass: "bg-green-600",
      reportName: t.import.requiredTableReportPipelineGeo,
      targetTable: t.import.targetTableRtbBidstream,
      description: t.import.exportGuideReport3Desc,
      dimensions: [
        t.import.exportGuideDimDay,
        t.import.exportGuideDimCountry,
        t.import.exportGuideDimHour,
      ],
      metrics: [
        t.import.exportGuideMetricBidRequests,
        t.import.exportGuideMetricInventoryMatches,
        t.import.exportGuideMetricSuccessfulResponses,
        t.import.exportGuideMetricBids,
        t.import.exportGuideMetricBidsInAuction,
        t.import.exportGuideMetricAuctionsWon,
        t.import.exportGuideMetricImpressions,
        t.import.exportGuideMetricClicks,
      ],
    },
    {
      id: "4",
      containerClass: "border-2 border-orange-200 rounded-lg p-4 bg-orange-50",
      badgeClass: "bg-orange-600",
      reportName: t.import.requiredTableReportPipeline,
      targetTable: t.import.targetTableRtbBidstream,
      description: t.import.exportGuideReport4Desc,
      dimensions: [
        t.import.exportGuideDimDay,
        t.import.exportGuideDimHour,
        t.import.exportGuideDimCountry,
        t.import.exportGuideDimPublisherId,
        t.import.exportGuideDimPublisherName,
      ],
      metrics: [
        t.import.exportGuideMetricBidRequests,
        t.import.exportGuideMetricInventoryMatches,
        t.import.exportGuideMetricSuccessfulResponses,
        t.import.exportGuideMetricReachedQueries,
        t.import.exportGuideMetricBids,
        t.import.exportGuideMetricBidsInAuction,
        t.import.exportGuideMetricAuctionsWon,
        t.import.exportGuideMetricImpressions,
        t.import.exportGuideMetricClicks,
      ],
    },
    {
      id: "5",
      containerClass: "border-2 border-red-200 rounded-lg p-4 bg-red-50",
      badgeClass: "bg-red-600",
      reportName: t.import.requiredTableReportBidFiltering,
      targetTable: t.import.targetTableRtbBidFiltering,
      description: t.import.exportGuideReport5Desc,
      dimensions: [
        t.import.exportGuideDimDay,
        t.import.exportGuideDimCountry,
        t.import.exportGuideDimCreativeId,
        t.import.exportGuideDimBidFilteringReason,
      ],
      metrics: [t.import.exportGuideMetricBids],
    },
  ] as const;

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

      {reportCards.map((report) => (
        <div key={report.id} className={report.containerClass}>
          <div className="flex items-center gap-2 mb-3">
            <span className={`${report.badgeClass} text-white text-xs font-bold px-2 py-1 rounded`}>
              {report.id}
            </span>
            <h4 className="font-semibold text-gray-900">{report.reportName}</h4>
            <span className="text-xs text-gray-500 ml-auto">{`→ ${report.targetTable}`}</span>
          </div>
          <p className="text-gray-600 mb-3">{report.description}</p>

          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideDimensions}</p>
              <ul className="space-y-1 text-gray-700">
                {report.dimensions.map((item, index) => (
                  <li key={`${report.id}-dim-${index}`}>• {item}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t.import.exportGuideMetrics}</p>
              <ul className="space-y-1 text-gray-700">
                {report.metrics.map((item, index) => (
                  <li key={`${report.id}-metric-${index}`}>• {item}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ))}

      {/* Naming Convention */}
      <div className="bg-gray-100 rounded-lg p-4">
        <h4 className="font-semibold text-gray-900 mb-2">{t.import.exportGuideReportNaming}</h4>
        <p className="text-gray-700 mb-2">
          {t.import.exportGuideNameYourReports}{" "}
          <code className="bg-white px-2 py-1 rounded border">catscan-{"{type}"}-{"{account_id}"}-yesterday-UTC</code>
        </p>
        <p className="text-gray-600 text-xs">
          {t.import.exportGuideExampleLabel}{" "}
          <code className="bg-white px-1 rounded">catscan-bidsinauction-1111111111-yesterday-UTC</code>
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

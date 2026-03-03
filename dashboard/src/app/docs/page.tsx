"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function DocsIndexPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      {/* Hero */}
      <h1 className="text-4xl font-bold text-gray-900 mb-3">
        What is Cat-Scan?
      </h1>
      <p className="text-lg text-gray-600 mb-2">
        A QPS optimization platform built exclusively for{" "}
        <strong className="text-gray-900">Google Authorized Buyers</strong>.
      </p>
      <p className="text-gray-500 mb-8">
        Cat-Scan gives you visibility into how your bidder&apos;s query-per-second
        allocation is being used (and wasted) and provides the
        tools to fix it.
      </p>

      {/* QPS Funnel SVG */}
      <div className="mb-10 rounded-lg overflow-hidden border border-gray-200">
        <img
          src="/docs/qps-funnel.svg"
          alt="QPS Funnel: Google sends bid requests, most miss your bidder. That's waste."
          className="w-full"
        />
      </div>

      {/* The problem */}
      <h2 className="text-2xl font-semibold text-gray-900 mb-3">The core problem</h2>
      <p className="text-gray-700 leading-7 mb-4">
        When you operate a seat on Google&apos;s Authorized Buyers exchange, Google
        sends your bidder a stream of bid requests. You pay for this stream: it
        consumes your allocated QPS, your bidder&apos;s compute, and your bandwidth.
      </p>
      <p className="text-gray-700 leading-7 mb-4">
        But not every bid request is useful. Many arrive for inventory you&apos;d
        never buy: countries you don&apos;t target, publishers you&apos;ve never heard of,
        ad sizes you have no creatives for. Your bidder still has to receive and
        reject each one.
      </p>
      <p className="text-gray-700 leading-7 mb-8">
        In a typical setup, <strong>more than half of your QPS is waste.</strong>
      </p>

      {/* What Cat-Scan does */}
      <h2 className="text-2xl font-semibold text-gray-900 mb-4">What Cat-Scan does</h2>
      <div className="grid gap-4 mb-10">
        <div className="border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-gray-900 mb-1">1. Visibility</h3>
          <p className="text-gray-600 text-sm leading-6">
            Rebuilds reporting from Google&apos;s CSV exports (there is no Reporting API)
            and shows the full RTB funnel: QPS, bids, wins, impressions, clicks,
            and spend, broken down by geography, publisher, ad size, creative, and
            pretargeting config.
          </p>
        </div>
        <div className="border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-gray-900 mb-1">2. Control</h3>
          <p className="text-gray-600 text-sm leading-6">
            Manage your 10 pretargeting configurations per seat with dry-run preview,
            change history, one-click rollback, and an optimizer that scores segments
            and proposes config changes.
          </p>
        </div>
        <div className="border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-gray-900 mb-1">3. Safety</h3>
          <p className="text-gray-600 text-sm leading-6">
            Every pretargeting change is recorded. Preview before applying, roll back
            instantly. The optimizer uses workflow presets (safe / balanced / aggressive)
            so no automated change goes live without human review.
          </p>
        </div>
      </div>

      {/* Key concepts */}
      <h2 className="text-2xl font-semibold text-gray-900 mb-4">Key concepts</h2>
      <div className="overflow-x-auto mb-10">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 pr-4 font-semibold text-gray-900">Concept</th>
              <th className="text-left py-2 font-semibold text-gray-900">What it means</th>
            </tr>
          </thead>
          <tbody className="text-gray-700">
            <tr className="border-b border-gray-100">
              <td className="py-2.5 pr-4 font-medium text-gray-900 whitespace-nowrap">Seat</td>
              <td className="py-2.5">A buyer account on Google Authorized Buyers, identified by a <code className="text-xs bg-gray-100 px-1 rounded">buyer_account_id</code>.</td>
            </tr>
            <tr className="border-b border-gray-100">
              <td className="py-2.5 pr-4 font-medium text-gray-900 whitespace-nowrap">QPS</td>
              <td className="py-2.5">Queries Per Second: the maximum rate of bid requests you ask Google to send. Google throttles the actual volume based on your account tier, so you want to use every request efficiently.</td>
            </tr>
            <tr className="border-b border-gray-100">
              <td className="py-2.5 pr-4 font-medium text-gray-900 whitespace-nowrap">Pretargeting</td>
              <td className="py-2.5">Server-side filters that tell Google what bid requests to send you. Controls geos, sizes, formats, platforms. 10 per seat.</td>
            </tr>
            <tr className="border-b border-gray-100">
              <td className="py-2.5 pr-4 font-medium text-gray-900 whitespace-nowrap">RTB Funnel</td>
              <td className="py-2.5">Bid request &rarr; bid &rarr; win &rarr; impression &rarr; click &rarr; conversion. Each step has drop-off; Cat-Scan shows where.</td>
            </tr>
            <tr>
              <td className="py-2.5 pr-4 font-medium text-gray-900 whitespace-nowrap">Waste</td>
              <td className="py-2.5">QPS consumed by bid requests your bidder can&apos;t or won&apos;t use. The goal is to reduce waste without losing valuable traffic.</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Track boxes */}
      <h2 className="text-2xl font-semibold text-gray-900 mb-4">Documentation tracks</h2>
      <div className="grid md:grid-cols-2 gap-4 mb-10">
        <Link
          href="/docs/01-logging-in"
          className="block border border-gray-200 rounded-lg p-6 hover:border-primary-300 hover:shadow-sm transition-all group"
        >
          <h3 className="text-lg font-semibold text-gray-900 mb-2 group-hover:text-primary-600">
            Media Buyer Docs
          </h3>
          <p className="text-sm text-gray-500 mb-4">
            Logging in, reading the QPS funnel, analyzing waste by geo/publisher/size,
            managing creatives, pretargeting, the optimizer, conversions, data import,
            and reports.
          </p>
          <span className="flex items-center gap-1 text-sm font-medium text-primary-600">
            Start reading <ArrowRight className="h-4 w-4" />
          </span>
        </Link>
        <Link
          href="/docs/11-architecture"
          className="block border border-gray-200 rounded-lg p-6 hover:border-primary-300 hover:shadow-sm transition-all group"
        >
          <h3 className="text-lg font-semibold text-gray-900 mb-2 group-hover:text-primary-600">
            DevOps Docs
          </h3>
          <p className="text-sm text-gray-500 mb-4">
            Architecture overview, deployment, health monitoring, database operations,
            troubleshooting, user administration, and integrations.
          </p>
          <span className="flex items-center gap-1 text-sm font-medium text-primary-600">
            Start reading <ArrowRight className="h-4 w-4" />
          </span>
        </Link>
      </div>
    </div>
  );
}

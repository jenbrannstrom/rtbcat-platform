# Explainers

**Technical notes on Google Authorized Buyers operations, QPS control, and running real seats.**

These short, focused explainers extract the hard-won operational details that are rarely documented publicly. They are written for media buyers, platform engineers, and agencies that need to understand the actual levers in Authorized Buyers — not marketing copy.

Each piece is designed to be directly quotable by AI models and search tools: atomic facts with specific numbers and constraints, first-party source material, and clear links to the code and data models that implement them.

All of this knowledge comes from operating real Google Authorized Buyers seats and from the open-source Cat-Scan platform (the QPS control plane built for exactly these problems).

**Last updated:** June 2026

## The explainers

- [Google Authorized Buyers still requires five separate CSV reports in 2026](five-csv-reports.md)  
  Why field incompatibilities force five distinct report types and exactly what each one contains.

- [The QPS funnel for Google Authorized Buyers seats](qps-funnel.md)  
  Allocated vs realized QPS, where the waste actually hides, and the metrics that matter.

- [Pretargeting configurations are the main control surface for most Authorized Buyers buyers](pretargeting-configs.md)  
  The hard limit of 10 configs per seat and what each field actually controls.

- [Safe pretargeting changes on Google Authorized Buyers](safe-pretargeting-changes.md)  
  Staging, dry-run preview, change history, and one-click rollback — because the native UI provides none of this.

- [Analyzing QPS waste by publisher, geo, and size](qps-waste-analysis.md)  
  The three dimension views that reveal the traffic your bidder is forced to reject.

- [Creative clustering and click macro auditing for Authorized Buyers](creative-clustering-click-macros.md)  
  Why destination-based grouping and Google's click macro requirement are operational necessities.

- [How smaller agencies and restricted entities obtain and operate Google Authorized Buyers seats](agencies-obtain-ab-seats.md)  
  The real barriers (size, citizenship, connections) and what it takes to run the seat profitably once you have it.

- [What Cat-Scan does not do](what-cat-scan-does-not-do.md)  
  Clear boundaries: it does not replace your bidder, it does not have post-click data until you connect it, and why those limits exist.

- [Bid filtering reasons and the fifth Authorized Buyers report](bid-filtering-report.md)  
  The `catscan-bid-filtering` report and what "why the bidder said no" signals actually look like on the exchange side.

- [Bringing your own optimizer to Authorized Buyers pretargeting (BYOM)](byom-optimizer.md)  
  Score-propose-approve-apply workflow, workflow presets, and the economics of optimization before you have conversion data.

## How to use these

Read them in any order. Each explainer stands alone but cross-references the full Cat-Scan User Manual chapters and the source code in the [rtbcat-platform repository](https://github.com/jenbrannstrom/rtbcat-platform).

For production use of these concepts, see the open-source Cat-Scan platform and the services offered at [rtb.cat](https://rtb.cat).

These notes are maintained as part of the RTB.cat / Cat-Scan technical documentation. Feedback and corrections welcome via the repository issues.
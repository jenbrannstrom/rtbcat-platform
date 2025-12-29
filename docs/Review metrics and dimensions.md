# Review metrics and dimensions - Authorized Buyers Help
When you create a report, you add metrics and dimensions to focus on the data that's important to you. For a report to run, you must add at least one metric. 

Examples of dimensions are "Country" and "Platform." Examples of metrics are "Bids" and "Impressions."

**Tip**: Certain dimensions and metrics are incompatible. To help prevent incompatible metrics and dimensions from being added to your report, click ![More options](https://storage.googleapis.com/support-kms-prod/5jVzMuY0cEZFiktRhY3PSm7czaLGlwlYmsKV) and enable "Show incompatible." 

To understand metrics and dimensions in greater detail, review the following tables. 

Dimensions
----------

Review dimensions

#### Time dimensions


|Dimension|Description                                                         |Filterable|
|---------|--------------------------------------------------------------------|----------|
|Month    |                    Activity by month. Can also be shown as a range.|No        |
|Week     |                    Activity by week. Can also be shown as a range. |No        |
|Day      |                    Activity by day. Can also be shown as a range.  |No        |
|Hour     |                    Activity by hour. Can also be shown as a range. |No        |


**Note:** UTC is fully supported for reports, starting with December 1, 2024. Earlier dates can't be selected.

#### Inventory dimensions



* Dimension: Country
  * Description:                     Shows the countries where users viewed ads on the publisher’s inventory.
  * Filterable: Yes
* Dimension: Creative format
  * Description:                     Shows the format of the creative served.
  * Filterable: Yes
* Dimension: Mobile app ID
  * Description:                     Shows the mobile app IDs on which mobile App impressions are served.
  * Filterable: Yes
* Dimension: Mobile app name
  * Description:                     Shows the mobile app names (from the iTunes app store or Google Play store) on which mobile app impressions are served (e.g., “The Best App”).
  * Filterable: Yes
* Dimension: Platform
  * Description:                     Displays the different types of devices and platforms (for example, desktop computer, a high-end mobile device or another mobile device) that advertisers serve ads on.
  * Filterable: Yes
* Dimension: Environment
  * Description: Shows environment, filterable to App or Web.
  * Filterable: Yes
* Dimension: Publisher domain
  * Description: Shows data for publisher domains and subdomains.
  * Filterable: Yes
* Dimension: Web property name
  * Description:                     Shows the seller names associated with the seller accounts for the pages on which ads are served.
  * Filterable: Yes
* Dimension: Creative policies
  * Description: Shows creative policies applied, such as the Ads Network and Platform Programs policies.
  * Filterable: Yes
* Dimension: Publisher protections
  * Description: Shows publisher protections.
  * Filterable: Yes
* Dimension: Buyer SDK
  * Description: Shows if ads are rendered with a buyer provided SDK.
  * Filterable: Yes
* Dimension: GMA SDK
  * Description: Shows if ads are rendered with the Google Mobile Ads SDK.
  * Filterable: Yes
* Dimension: Publisher name
  * Description: The name of the publisher as it is known to Google.
  * Filterable: Yes
* Dimension: Publisher ID
  * Description: The ID used to identify the publisher on Google's sell-side platform. This is identical to the ID present in the publisher's ads.txt or app-ads.txt file.
  * Filterable: Yes


#### Demand dimensions



* Dimension: Advertiser
  * Description:                     Shows which advertisers transacted on publisher inventory and for how much.
  * Filterable: Yes
* Dimension: Bid filtering reason
  * Description:                     Shows reason why a bid was filtered.
  * Filterable: Yes
* Dimension: Billing ID
  * Description:                     Shows the billing ID used to transact on publisher inventory.
  * Filterable: Yes
* Dimension: Buyer account ID
  * Description:                     Shows which buyers (account ID) transacted on publisher inventory.
  * Filterable: Yes
* Dimension: Buyer account name
  * Description:                     Shows which buyers (account name) transacted on publisher inventory.
  * Filterable: Yes
* Dimension: Buyer reporting ID
  * Description:                     Shows which buyers (reporting ID) transacted on publisher inventory.
  * Filterable: Yes
* Dimension: Creative ID
  * Description:                     Shows the buyer creative ID assigned to each creative.
  * Filterable: No
* Dimension: Creative size
  * Description:                     Shows the actual winning ad size of the creative. Here are additional creative size labels:                      Native when the ad call is stylized like the surrounding app or page content.            Rewarded when the ad call offers an option to watch a video in order to receive a reward from the publisher.            Interstitial when the ad call is a full-screen video ad that appears in between experiences in an app.            Dynamic when the ad call is filled by a Google ad. This label is applied when the creatives have no defined size, such as a text ad.            Video/Overlay when the ad call is an overlay ad inside a video player.            Unmatched when the ad requests are not matched with an ad.                    
  * Filterable: Yes
* Dimension: Delivered by Protected Audience API
  * Description:           Shows impressions won by bids from Protected Audience interest groups. Learn more about the Protected Audience API.           Note: This dimension is only supported for impression metrics; bid metrics are not supported.
  * Filterable: Yes
* Dimension: VAST error code
  * Description:                     Displays the VAST error code.
  * Filterable: Yes


#### Deal dimensions



* Dimension: Deal ID
  * Description:                     Shows the performance breakdown of Preferred Deals, Private Auctions, and Programmatic Guaranteed deals, broken out by deal ID. The deal ID is a system-generated number used to identify a deal between a buyer and a publisher. The ID is included in all bid requests that are passed as part of Preferred Deals, Private Auctions, and Programmatic Guaranteed deals.
  * Filterable: Yes
* Dimension: Deal name
  * Description:                     Shows the performance of Preferred Deals, broken out by a deal name.
  * Filterable: Yes
* Dimension: Transaction type
  * Description:                     Shows the transaction/auction type of the ad (Open auction, private auction, preferred deal, programmatic reservation).
  * Filterable: Yes
* Dimension: Cost type
  * Description: Shows the cost type of the ad (CPM or CPD).
  * Filterable: Yes


Metrics 
--------

Review metrics

#### Bid metrics



* Metric: Inventory matches
  * Description: The total number of potential queries based on your pretargeting settings.
* Metric: Bid requests
  * Description: The total number of bid requests sent to the bidder.
* Metric: Successful responses
  * Description: The total number of properly formed bid responses received by our servers within 100 ms.
* Metric: Bids
  * Description: The total number of bids received from the bidder.
* Metric: Bids in auction
  * Description: The total number of bids that passed through all filters and competed in the auction.
* Metric: Auctions won
  * Description: The total number of impressions the bidder won.
* Metric: Reached queries
  * Description: The total number of ad queries on which your bidder won both the real-time auction and the mediation chain. For queries that participated in mediation, reached queries equals the total number of times your bidder won in mediation. For queries that did not participate in mediation, reached queries equals auctions won. Learn more about Mediation.
* Metric: Bid filtering opportunity cost (Bidder currency)
  * Description:                     The additional amount the bidder would transact if the bids with this creative were not filtered. Examples include, due to publisher controls and policies in the bidder's currency.
* Metric: Bid filtering opportunity cost (Buyer currency)
  * Description:                     The additional amount the bidder would transact if the bids with this creative were not filtered. Examples include, due to publisher controls and policies, in the buyer's currency.


#### Impression metrics



* Metric: Impressions
  * Description: The count of ads which are served to a user          In the context of video, this metric measures the number of video ads actually recorded as "viewed" or showing the first frame of the video ad, not showing the ad to completion. Ad impressions are often less than matched requests because in some cases, matched requests may include video ads that never show the first frame (for example, due to an ad serving error or some other technical issue).          
* Metric: Clicks
  * Description: The number of times a user clicked on an ad
* Metric: Active view measurable
  * Description:                     Impressions (out of all eligible impressions) that can be measured by Active View
* Metric: Active view viewable
  * Description:                     Impressions (out of all measurable impressions that were considered viewable based on MRC standards) that can be viewed
* Metric: Active view viewability rate
  * Description:                     Active View viewability rate is the ratio of Viewable impressions to Measurable impressions                    Active View viewability rate = Viewable impressions / Measurable impressions
* Metric:                     Spend (bidder currency)
  * Description: Cost of the ad impression, or daily cost for CPD deals (in the bidder's currency)
* Metric:                     Spend (buyer currency)
  * Description: Cost of the ad impression, or daily cost for CPD deals (in the buyer's currency)
* Metric:                     CPM (bidder currency)
  * Description:                     Cost per thousand impressions. (in the bidder's currency)                    CPM = (Cost / Ad impressions) * 1000
* Metric:                     CPM (buyer currency)
  * Description:                     Cost per thousand impressions. (in the buyer's currency)                    CPM = (Cost / Ad impressions) * 1000
* Metric:                     CPC (bidder currency)
  * Description:                     The cost-per-click (CPC) is the average amount you pay each time a user clicks on your ad. (in the bidder's currency)
* Metric:                     CPC (buyer currency)
  * Description:                     The cost-per-click (CPC) is the average amount you pay each time a user clicks on your ad. (in the buyer's currency)


#### Video viewership metrics



* Metric: Video starts
  * Description: Displays a count of how many times the video ad started playing.
* Metric: Video reached first quartile
  * Description: Measures the effectiveness of video ads by determining what percentage of a given video was played. Ad Exchange for Video displays a count of how many times the first 25% (Quartile 1) of a video ad has been played.
* Metric: Video reached midpoint
  * Description: Measures the effectiveness of video ads by determining what percentage of a given video was viewed by a user. Ad Exchange for Video displays a count of how many users have seen 50% (Midpoint) of a video ad.
* Metric: Video reached third quartile
  * Description: Measures the effectiveness of video ads by determining what percentage of a given video was played. Ad Exchange for Video displays a count of how many times the first 75% (Quartile 3) of a video ad has been played.
* Metric: Video completions
  * Description: Displays a count of how many times 100% of a video ad has been played.
* Metric: VAST error count
  * Description: Displays a count of how many VAST errors occurred during a video ad.
* Metric: Engaged views
  * Description:                     Number of times a skippable video ad has been viewed to completion or watched to 30 seconds, whichever happens first.
* Metric: View-through rate
  * Description:                     View-through rate is the ratio of engaged views to skippable impressions.                    View-through rate = Engaged views / Skippable ad impressions.


#### Cost transparency metrics



* Metric: Raw impressions
  * Description:                               Number of impression pings from user devices.
* Metric:                     Deduplicated impressions
  * Description:                     Number of deduplicated impression pings.
* Metric: Cost of deduplicated impressions (bidder currency)
  * Description:                     The cost corresponding to deduplicated impressions. (in the bidder's currency)
* Metric: Cost of deduplicated impressions (buyer currency)
  * Description:                     The cost corresponding to deduplicated impressions. (in the buyer's currency)
* Metric: Pre-filtered impressions
  * Description:                     Number of invalid impressions pre-filtered near real time that were not billed for (online spam).
* Metric: Cost of pre-filtered impressions (bidder currency)
  * Description:                     The cost of invalid impressions pre-filtered in near real time that were not billed for (online spam). (in the bidder's currency)
* Metric: Cost of pre-filtered impressions (buyer currency)
  * Description:                     The cost of invalid impressions pre-filtered in near real time that were not billed for (online spam). (in the buyer's currency)
* Metric: Impressions net of pre-filtering
  * Description:                     Top-line number of impressions that appears in the invoice, which excludes IVT pre-filtered impressions.
* Metric:                     Cost net of pre-filtering (bidder currency)
  * Description:                     Top-line cost that appears in the invoice, which excludes IVT pre-filtered cost. (in the bidder's currency)
* Metric:                     Cost net of pre-filtering (buyer currency)
  * Description:                     Top-line cost that appears in the invoice, which excludes IVT pre-filtered cost. (in the buyer's currency)
* Metric: IVT credited impressions
  * Description: The number of impressions detected to be invalid after serving that were then credited back to your account (offline spam).
* Metric: Cost of IVT credited impressions (bidder currency)
  * Description: The cost of invalid impressions detected to be invalid after serving that were then credited back to your account (offline spam). (in the bidder's currency)
* Metric: Cost of IVT credited impressions (buyer currency)
  * Description: The cost of invalid impressions detected to be invalid after serving that were credited back to your account (offline spam). (in the buyer's currency)
* Metric: Billed impressions
  * Description: Bottom-line impression count after removing all spam-related impression credits.
* Metric: Cost of billed impressions (bidder currency)
  * Description: Bottom-line cost that appears in the invoice, which excludes both online and offline spam filtering. (in the bidder's currency)
* Metric: Cost of billed impressions (buyer currency)
  * Description: Bottom-line cost that appears in the invoice, which excludes both online and offline spam filtering. (in the buyer's currency)


**Request other data**

If you still have questions about the data available to you and/or how to access the data, please use this [form](https://support.google.com/admanager/contact/ads_cps_sellside).

Was this helpful?
-----------------

How can we improve it?

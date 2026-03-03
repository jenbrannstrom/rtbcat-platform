# Chapter 7: The Optimizer (BYOM)

*Audience: media buyers, optimization engineers*

The optimizer is Cat-Scan's automated optimization engine. "BYOM" stands for
Bring Your Own Model: you register an external scoring endpoint, and
Cat-Scan uses it to generate config change proposals.

## How it works

```
  Score          Propose          Review          Apply
────────────> ────────────> ────────────> ────────────>
Your model     Cat-Scan       You (human)    Google AB
evaluates      generates      approve or     config is
segments       config         reject         updated
               changes
```

1. **Score**: Cat-Scan sends segment data to your model endpoint. The model
   returns a score for each segment (geo, size, publisher).
2. **Propose**: Based on scores, Cat-Scan generates specific pretargeting
   config changes (e.g., "exclude these 5 geos", "add these 3 sizes").
3. **Review**: You see the proposal with projected impact. You approve or
   reject.
4. **Apply**: Approved proposals are applied to the pretargeting config on
   Google's side. The change is recorded in the history.

## Model management

### Registering a model

Go to `/settings/system` and find the Optimizer section.

1. Click **Register Model**.
2. Fill in: name, model type, endpoint URL (your scoring service).
3. The endpoint must accept POST requests with segment data and return
   scored results.
4. Save.

### Validating the endpoint

Before activating, test your model:

1. Click **Validate endpoint** on the model card.
2. Cat-Scan sends a test payload to your endpoint.
3. Results show: response time, response format validity, score distribution.
4. Fix any issues before activating.

### Activating and deactivating

- **Activate**: the model becomes the active scorer for this seat.
- **Deactivate**: the model stops being used, but its configuration is
  preserved. Only one model can be active per seat at a time.

## Workflow presets

When running score-and-propose, you choose a preset:

| Preset | Behavior | When to use |
|--------|----------|-------------|
| **Safe** | Only proposes changes with high confidence and low risk. Smaller improvements, lower chance of mistakes. | First time using the optimizer, or conservative accounts. |
| **Balanced** | Moderate confidence threshold. Good trade-off between impact and safety. | Default for most usage. |
| **Aggressive** | Proposes larger changes with higher potential impact. More risk of over-optimization. | Experienced users who monitor daily and can roll back quickly. |

## Economics

The optimizer also tracks the economics of optimization:

- **Effective CPM**: what you're actually paying per thousand impressions,
  accounting for waste.
- **Hosting cost baseline**: your bidder's infrastructure cost, configured in
  the optimizer setup. Used to calculate whether savings from QPS reduction
  offset hosting.
- **Efficiency summary**: overall ratio of useful QPS to total QPS.

Configure your hosting cost at `/settings/system` > Optimizer Setup.

## Reviewing proposals

Each proposal shows:
- **Segment scores** that drove the recommendation
- **Specific changes** to pretargeting fields (adds, removes, updates)
- **Projected impact** on QPS, waste ratio, and spend

You can:
- **Approve**: marks the proposal as accepted
- **Apply**: pushes the approved changes to Google
- **Reject**: discards the proposal
- **Check apply status**: verify the changes took effect on Google's side

## Related

- [Pretargeting Configuration](06-pretargeting.md): the configs the optimizer
  modifies
- [Conversions and Attribution](08-conversions.md): conversion data feeds
  into scoring quality
- [Reading Your Reports](10-reading-reports.md): tracking optimizer impact

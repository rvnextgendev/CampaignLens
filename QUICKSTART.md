# Try the two scenarios

## Boutique clothing

Select **Boutique clothing**. The sample brand is Tara Boutique Clothing selling a handcrafted cotton kurta.

Its example files are in `examples/boutique/`. Discuss whether altered/custom-fit items can be returned, how coupons interact, and how affiliate commissions change after cheaper exchanges. The engine will not decide those policies for you.

## Footwear

Select **Footwear**. The sample is ABC Boutique Footwear. Example files are in `examples/footwear/`. Discuss sizing exchanges, worn-item conditions, payout timing and commission recovery.

## Demonstrate an improvement

1. Keep the baseline unchanged.
2. In the proposed campaign, reduce `discount_pct` by 5 percentage points.
3. Answer coupon stacking as `disallow`, affiliate attribution as `last_touch`, and exchange commission as `recalculate` if these are genuinely the owner's intended rules.
4. Recalculate. Compare normal-sale and return contributions. A higher price may change demand: the tool does NOT predict this.
5. Use the offline demo to inspect five review panels without an API key. Its findings are fixtures, not an assessment of the changed economics.
6. To get actual AI reviews, enter your Groq key and run five agents.
7. Save the review snapshot, then record the owner's decision with a reason. Pilot acceptance requires five completed live reviews and no unknown policy enums. That gate is a workflow check, not assurance of a good business decision.

## Your own context

`brand.json` holds exact numbers and policy choices. `business_context.txt` holds your goals and questions. `return_policy.md` holds the rules your customers/affiliates currently see. CSV contains anonymized actual ledger data. Keep them consistent; discrepancies should be investigated, not silently corrected by AI.

The exact evidence each agent may cite is visible under **Evidence references available to agents**. Agent citations are validated by ID only; check the underlying text or calculation yourself.

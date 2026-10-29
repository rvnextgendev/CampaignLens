# CampaignLens

**See the impact before you launch.**

A local review application for boutique clothing, footwear and future retail brands. It combines deterministic calculations, uploaded policy and order evidence, five independently executed AI reviewers, and recorded human decisions.

## Quick start — Windows, Python 3.12+

Extract the ZIP and open a terminal inside `campaignlens` (the folder containing `app.py`).

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py --server.port 8505
```

Open http://localhost:8505. On macOS/Linux, use `python3 -m venv .venv` and `.venv/bin/python` for the subsequent commands.

1. Select **Footwear** or **Boutique clothing** in the sidebar.
2. Inspect the baseline and proposed campaign JSON. Change the proposed discount, cost or policy to test an alternative.
3. Answer the missing-policy questions, or keep them unknown to see the gaps.
4. Review business notes and the policy document. Keep numerical assumptions consistent with JSON.
5. Use the fictional sample CSV or upload anonymized actual orders using the exact template.
6. Click **Calculate & compare**. View scenario differences, campaign sensitivity and order timelines.
7. Open **Five reviewers**. Run the offline demo to check the workflow, or enter your Groq key and run five live agents.
8. Save a snapshot. In **Saved decisions**, enter a reviewer name, decision and reason. Export the record if needed.

The offline demo is explicitly a deterministic fixture, not AI advice. It cannot satisfy the live-review requirement for `accepted_for_pilot`. That decision also requires all configured policy questions to be resolved. `needs_changes` and `rejected` can be recorded without live AI review. A recorded decision does not launch anything.

## Included examples

| Brand | Category | Example questions |
| --- | --- | --- |
| ABC Boutique Footwear | footwear | Sizing exchanges, worn returns, reverse shipping and payout recovery |
| Tara Boutique Clothing | boutique_apparel | Altered/custom-fit garments, made-to-order eligibility, fit corrections and exchange commission |

Both include the following fictional files:

- `brand.json`: versioned brand identity, category, questions and exact calculation inputs.
- `business_context.txt`: goals, assumptions, exceptions and questions for reviewers.
- `return_policy.md`: policy evidence, including deliberately unresolved terms.
- `historical_orders.csv`: six fictional ledger rows covering kept, returned, exchanged, RTO and partial-refund outcomes.

Boutique-specific exceptions are questions and policy evidence in this version. The engine does not automatically decide whether altered clothing or worn footwear qualifies for a refund.

## What does the LLM receive?

Each agent has a separate system instruction and its own API call. Each receives the same versioned bundle of:

- Selected brand and category questions.
- Baseline and candidate inputs plus Python calculation results and assumptions.
- Numbered business-context and policy lines.
- Historical summary and the 20 lowest-contribution order rows, including ledger values and event dates.
- Known missing-policy questions and evidence source IDs.

There are five independent reviewers: **owner, finance, affiliate, customer, operations**. Each returns structured JSON with a summary and findings: issue, severity, evidence IDs, impact, suggested action, and question for the owner. The parser checks schema and source-ID existence. It does not establish that a citation actually proves the model's claim; a human must check that.

The coordinator is deterministic Python: it collects findings, sorts by severity and preserves each role's perspective. It does not run a sixth LLM call, approve campaigns, or pretend the agents are independent human experts. There is no debate round. Failed reviewers do not discard successful results.

No key is needed for calculations, CSV analysis or the offline demo. Live reviews use Groq with five calls, at most two concurrent, plus provider retries. Your context, policy and selected evidence are sent to Groq when you explicitly run the live review. Do not include customer identities or other sensitive material.

## Groq key

Enter a key in the sidebar, or copy `.env.example` to `.env` and set `GROQ_API_KEY`. Streamlit Cloud can also read `GROQ_API_KEY` from its secrets. Sidebar credentials remain session-specific and are not written into a snapshot by the application.

Default model: `openai/gpt-oss-120b`, using strict JSON schema responses. Model availability and limits depend on the provider/account. Local orchestration is asynchronous Python rather than LangGraph; the small provider interface makes future orchestration changes possible without changing the calculation engine.

## Add another brand without editing Python

1. Copy either example `brand.json`.
2. Assign a new `brand_id`, such as `lotus_clothing`.
3. Change `display_name` and matching `campaign.business_name`.
4. Choose `footwear`, `boutique_apparel` or `general_retail`. Change product costs, campaign assumptions and custom questions.
5. Select **Custom brand** and upload the JSON. Upload its own notes, policies and CSV, whose `brand_id` must match.

Version 1 supports **INR and the existing retail contribution model**. A new brand that fits that model requires configuration only. Subscriptions, consumables, rental, other currencies, multiple SKUs or new financial rules require schema/engine extensions and tests. Do not force unrelated business models into the footwear formulas.

## Calculation and comparison semantics

All money excludes GST/taxes. `15` means 15%, not 0.15. Decimal precision is retained until final output rounding. Some displayed rounded line items may differ by one paisa from their displayed total.

- Net sales = list price × (1 − campaign discount).
- Stacked discounts (when sequential) multiply the two discount factors.
- Normal contribution = net sales − product cost − shipping − packaging − payment fee − affiliate commission.
- Full-return contribution = negative sum of shipping, packaging, reverse shipping, handling, lost inventory value, nonrefunded fee and retained commission. Full net sales are refunded.
- Commission recovery depends on both reversal policy and post-payout clawback.
- Exchange contribution uses replacement net sales/product cost, old-item inventory loss, two packs, original/replacement/reverse shipping, handling, original payment fee and the selected commission treatment. It assumes the net-price difference is refunded; no new processing fee applies.
- Campaign sensitivity = order volume × weighted normal/full-return contribution − campaign fixed cost. It presents all-returns-before-payout and all-returns-after-payout bounds at two configured return rates.

Scenario comparison shows per-order contribution changes. Baseline and candidate projections retain their own configured order volumes, return rates and fixed budgets; keep these equal to isolate a policy change. The app does not automatically calibrate or forecast demand from the historical sample.

Missing rules stay null/`needs_policy`. Attribution choices document a rule; the engine does not receive actual click events and cannot adjudicate a real affiliate claim.

Planned sensitivity excludes exchanges, partial refunds and COD/RTO; those outcomes are supported as **actual historical ledger rows**, not probability-weighted forecasts. It also excludes taxes, customer-paid shipping, financing, additional overheads and repeat returns. This is contribution, not accounting profit, cash-flow or a sales-success prediction. All planning timing intervals start at delivery.

## Historical CSV contract

Use the exact supplied header and column order. UTF-8; maximum 2 MB / 10,000 rows; one brand per upload; unique order IDs. No customer names, addresses or emails. All monetary fields must be explicitly supplied, non-negative and tax-exclusive; use 0 only when it is known to be zero.

| Fields | Meaning |
| --- | --- |
| `brand_id`, `order_id` | Exact selected brand ID and anonymized order identifier |
| `status` | `kept`, `returned`, `exchange`, `rto`, `partial_refund` |
| `payment_method` | `prepaid` or `cod` |
| `delivered_on`, `payout_on`, `returned_on`, `refund_on` | YYYY-MM-DD or blank when event did not occur; events are displayed by date, not executed |
| `net_sales` | Product revenue collected, after discounts and before refunds; not already net of `refund` |
| `refund` | Product refund paid |
| `product_cost` | Original acquisition cost; for an exchange include BOTH original and replacement item costs |
| `inventory_recovery` | Cost value recovered into stock, not cash or resale price; never double-count this by reducing `product_cost` too |
| `outbound_shipping`, `packaging` | Total actual charges; exchange rows include replacement shipping/packaging |
| `reverse_shipping`, `handling` | Actual reverse logistics and handling costs |
| `payment_fee` | Final fee expense after any fee refunds |
| `commission_paid`, `commission_recovered` | Actual paid commission and separately recovered amount |

Historical contribution = collected sales − refund − acquisition cost + inventory recovery − logistics/packaging/handling/fees − paid commission + recovered commission. Historical fixed overheads are not deducted. Full-return rate uses delivered orders as its denominator and excludes exchanges, partial refunds and RTO from its numerator.

CSV data is user-supplied and not independently verified. Order timelines omit events not represented by the four date columns. Same-day events have no time-of-day ordering. A SHA-256 source digest records the exact uploaded CSV bytes after UTF-8 decoding; it does not certify authenticity.

## Saved decisions and deployment scope

SQLite under `data/reviews.sqlite3` stores immutable-by-application review snapshots and append-only decision records. Override the path with `CAMPAIGNLENS_DB`. Use persistent disk if deploying locally; ephemeral hosting can lose the database. Exported records are ordinary JSON files.

Every history query is scoped to a brand ID, and changing brands clears active results. **This is not secure multi-tenancy**: anyone running this local app can select brands and self-report a reviewer name. There is no authentication, identity verification or authorization. Snapshot/decision records are not tamper-proof against a person who can edit SQLite. Do not deploy this prototype publicly with private data.

## Extension points

| Module | Responsibility / extension |
| --- | --- |
| `profiles.py` | Versioned brand config and category guidance |
| `engine.py` | Deterministic Decimal financial scenarios; add new financial rules here with tests |
| `history.py` | Strict historical CSV adapter; add Shopify or other import adapters separately |
| `evidence.py` | Sources, provenance, scenario comparison and review bundle |
| `agents.py` | Role prompts, structured review schema, provider interface and failure handling |
| `demo.py` | Clearly labelled offline test fixtures |
| `store.py` | Local persistence; replace with authenticated, tenant-scoped database access for SaaS |
| `app.py` | Streamlit workflow, uploads, evidence display and human decision recording |

A future SaaS release needs login, server-enforced tenant access, reviewer roles, durable storage, background jobs, usage limits, data-retention/deletion controls and deployment tests. These are not claimed as working features here. Real order integrations, payments, policy enforcement, PDF/DOCX ingestion and launch automation are also not included.

## Tests

From this folder:

```powershell
python -m unittest discover -s tests -v
```

Tests cover financial calculations, two category examples, a future brand from configuration, cross-brand CSV rejection, ledger contribution/timelines, five independent review calls, partial failures, fabricated source IDs, local history scoping, decision gates and Streamlit's end-to-end demo/save/brand-switch flow. All provider outputs used by tests are mocks; live Groq behavior needs your key.

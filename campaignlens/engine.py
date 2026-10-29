"""Deterministic campaign economics. Money is INR, excluding GST/taxes."""
from dataclasses import dataclass, asdict, fields
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json

D = Decimal
ZERO = D('0')
CENT = D('0.01')


def money(value):
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Campaign:
    business_name: str
    product_name: str
    list_price: str
    product_cost: str
    discount_pct: str
    coupon_pct: str
    commission_pct: str
    commission_base: str
    shipping_cost: str
    packaging_cost: str
    payment_fee_pct: str
    payment_fee_refund_pct: str
    return_shipping_cost: str
    return_handling_cost: str
    return_product_loss_pct: str
    return_rate_pct: str
    stress_return_rate_pct: str
    expected_orders: int
    campaign_fixed_cost: str
    return_window_days: int
    payout_delay_days: int
    stacking_policy: str
    returned_commission_policy: str
    post_payout_clawback: str
    attribution_rule: str
    exchange_commission_rule: str
    exchange_list_price: str
    exchange_product_cost: str
    exchange_shipping_cost: str
    exchange_handling_cost: str
    minimum_contribution: str

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError('Context must be a JSON object.')
        expected = {f.name for f in fields(cls)}
        if set(data) != expected:
            raise ValueError(f'Missing fields: {sorted(expected-set(data))}; unknown fields: {sorted(set(data)-expected)}')
        names = ['business_name', 'product_name']
        if any(not isinstance(data[n], str) or not data[n].strip() for n in names):
            raise ValueError('Business and product names are required.')
        choices = {
            'commission_base': ['net_sales', 'list_price'],
            'stacking_policy': ['disallow', 'sequential', 'unknown'],
            'returned_commission_policy': ['reverse', 'retain', 'unknown'],
            'post_payout_clawback': ['yes', 'no', 'unknown'],
            'attribution_rule': ['first_touch', 'last_touch', 'manual', 'unknown'],
            'exchange_commission_rule': ['recalculate', 'keep_original', 'unknown'],
        }
        integers = ['expected_orders', 'return_window_days', 'payout_delay_days']
        for name in integers:
            if type(data[name]) is not int or data[name] < (1 if name == 'expected_orders' else 0):
                raise ValueError(f'{name} must be a non-negative integer (orders must be positive).')
        if data['expected_orders'] > 1_000_000:
            raise ValueError('expected_orders cannot exceed 1,000,000.')
        for name, allowed in choices.items():
            if data[name] not in allowed:
                raise ValueError(f'{name} must be one of {allowed}.')
        for name in expected - set(names) - set(choices) - set(integers):
            if isinstance(data[name], bool):
                raise ValueError(f'{name} must be numeric.')
            try:
                value = D(str(data[name]))
            except (InvalidOperation, ValueError):
                raise ValueError(f'{name} must be numeric.') from None
            if not value.is_finite() or value < 0 or value > D('1000000000'):
                raise ValueError(f'{name} must be finite and between zero and 1,000,000,000.')
            if name.endswith('_pct') and value > 100:
                raise ValueError(f'{name} must be between 0 and 100.')
            if value.as_tuple().exponent < -4:
                raise ValueError(f'{name} supports at most four decimal places.')
        if D(str(data['list_price'])) <= 0:
            raise ValueError('list_price must be positive.')
        return cls(**{k: (str(v) if k not in integers and k not in names and k not in choices else v) for k,v in data.items()})

    def n(self, name):
        return D(str(getattr(self, name)))

    def rate(self, name):
        return self.n(name) / 100


def sale(c, *, coupon=False, duplicate=False):
    revenue = c.n('list_price') * (1-c.rate('discount_pct'))
    if coupon:
        revenue *= 1-c.rate('coupon_pct')
    base = revenue if c.commission_base == 'net_sales' else c.n('list_price')
    commission = base * c.rate('commission_pct') * (2 if duplicate else 1)
    fee = revenue * c.rate('payment_fee_pct')
    contribution = revenue - c.n('product_cost') - c.n('shipping_cost') - c.n('packaging_cost') - fee - commission
    return {'net_sales': revenue, 'commission': commission, 'payment_fee': fee, 'contribution': contribution}


def returned(c, sold, *, after_payout):
    # Full customer refund; recovered inventory is an asset, not revenue.
    if c.returned_commission_policy == 'unknown':
        return None
    commission = sold['commission']
    if c.returned_commission_policy == 'reverse':
        if not after_payout or c.post_payout_clawback == 'yes':
            commission = ZERO
        elif c.post_payout_clawback == 'unknown':
            return None
    loss = (c.n('product_cost') * c.rate('return_product_loss_pct')
            + c.n('shipping_cost') + c.n('packaging_cost')
            + c.n('return_shipping_cost') + c.n('return_handling_cost')
            + sold['payment_fee'] * (1-c.rate('payment_fee_refund_pct')) + commission)
    return -loss


def exchanged(c, sold):
    if c.exchange_commission_rule == 'unknown':
        return None
    revenue = c.n('exchange_list_price') * (1-c.rate('discount_pct'))
    if revenue > sold['net_sales']:
        raise ValueError('The cheaper-product exchange scenario requires exchange net price <= original net price.')
    base = revenue if c.commission_base == 'net_sales' else c.n('exchange_list_price')
    commission = (base * c.rate('commission_pct') if c.exchange_commission_rule == 'recalculate' else sold['commission'])
    # Original item restocked subject to loss; original processing fee retained in full.
    contribution = (revenue - c.n('exchange_product_cost')
                    - c.n('product_cost') * c.rate('return_product_loss_pct')
                    - c.n('shipping_cost') - 2*c.n('packaging_cost')
                    - c.n('return_shipping_cost') - c.n('exchange_shipping_cost')
                    - c.n('exchange_handling_cost') - sold['payment_fee'] - commission)
    return contribution


def simulate(c):
    sold = sale(c)
    gaps = []
    scenarios = []

    def row(name, value, explanation):
        scenarios.append({'scenario': name, 'status': 'needs_policy' if value is None else 'calculated',
                          'contribution_inr': None if value is None else money(value), 'explanation': explanation})

    row('Normal completed sale', sold['contribution'], 'One discounted order, one affiliate, no return or exchange.')
    before = returned(c, sold, after_payout=False)
    after = returned(c, sold, after_payout=True)
    row('Full return before payout', before, 'Full net-sales refund. Commission reversal depends on your policy; inventory recovery follows the supplied loss percentage.')
    row('Full return after payout', after, 'Commission is recovered only when reversal and post-payout clawback are both configured.')
    if c.stacking_policy == 'unknown':
        row('Coupon plus campaign discount', None, 'Choose disallow or sequential before enabling overlapping discounts.')
        gaps.append('Discount stacking is unspecified. Confirm whether the extra coupon is allowed.')
    elif c.stacking_policy == 'disallow':
        row('Coupon plus campaign discount', sold['contribution'], 'Extra coupon rejected; campaign discount still applies.')
    else:
        row('Coupon plus campaign discount', sale(c, coupon=True)['contribution'], 'Sequential discounts: price × (1-campaign discount) × (1-coupon discount).')
    row('Accidental double affiliate payout', sale(c, duplicate=True)['contribution'], 'Stress scenario only: two full commissions paid on one sale. Not an authorized payout decision.')
    row('Exchange for cheaper product', exchanged(c, sold), 'Same campaign discount on replacement. Original fee retained, two packs, reverse and replacement shipping, old-item loss, one exchange handling charge. Net price difference refunded.')
    if c.returned_commission_policy == 'unknown':
        gaps.append('Returned-order commission policy is missing; return contribution is unresolved.')
    if c.returned_commission_policy == 'reverse' and c.post_payout_clawback == 'unknown':
        gaps.append('Post-payout commission recovery is unspecified; late-return exposure is unresolved.')
    if c.returned_commission_policy == 'reverse' and c.post_payout_clawback == 'no':
        gaps.append('Paid commission cannot be recovered under this scenario; late returns retain the commission cost.')
    if c.payout_delay_days < c.return_window_days:
        gaps.append('Affiliate payout occurs before the return window closes. Review late-return exposure and recovery terms.')
    if c.attribution_rule in ['unknown', 'manual']:
        gaps.append('Competing affiliate claims need a documented decision; do not automatically pay both.')
    if c.exchange_commission_rule == 'unknown':
        gaps.append('Exchange commission policy is missing. Choose recalculate or keep_original.')
    if sold['contribution'] < c.n('minimum_contribution'):
        gaps.append('Normal sale contribution is below your configured minimum.')
    monthly = []
    for timing, return_value in [('all_returns_before_payout', before), ('all_returns_after_payout', after)]:
        for field in ['return_rate_pct', 'stress_return_rate_pct']:
            rate = c.rate(field)
            # These are two bounding timing assumptions, not a forecast of actual timing.
            value = None if return_value is None else ((1-rate)*sold['contribution']+rate*return_value)*c.expected_orders-c.n('campaign_fixed_cost')
            monthly.append({'timing_assumption': timing, 'return_rate_pct': str(c.n(field)),
                            'campaign_contribution_inr': None if value is None else money(value)})
    context = asdict(c)
    fingerprint = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
    return {'context_sha256': fingerprint, 'currency': 'INR', 'inputs': context,
            'sale_breakdown_inr': {k: money(v) for k,v in sold.items()},
            'scenarios': scenarios, 'policy_gaps': gaps, 'campaign_sensitivity': monthly,
            'assumptions': [
                'All prices and costs exclude taxes. No tax advice or tax calculation is performed.',
                'Contribution is not accounting profit or cash balance. Other overheads are excluded unless entered as campaign_fixed_cost.',
                'Return rate counts full refunds only. Exchanges, extra coupons and duplicate payouts are separate scenarios, excluded from campaign totals.',
                'Returned inventory recovers original product cost times (1-loss percentage); recovery may not be immediate cash.',
                'No new processing fee on replacement; original processing fee retained in full for exchanges.',
                'Payout delay and return window are assumed measured from delivery. No carrier delay, payout batch delay or COD/RTO is modeled.',
                'Policies are user-provided assumptions, not verified platform rules or enforced transactions.',
            ]}

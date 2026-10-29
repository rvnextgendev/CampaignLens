import json
from pathlib import Path
import unittest
from decimal import Decimal as D
from campaignlens.engine import Campaign, simulate, sale, returned, exchanged


SAMPLE = json.loads((Path(__file__).resolve().parents[1]/'examples/footwear/brand.json').read_text())['campaign']


def config(**changes):
    return Campaign.from_dict({**SAMPLE, **changes})


class Calculations(unittest.TestCase):
    def test_normal_sale(self):
        result = simulate(config())
        self.assertEqual(result['sale_breakdown_inr']['net_sales'], '1699.15')
        self.assertEqual(result['sale_breakdown_inr']['commission'], '203.90')
        self.assertEqual(result['sale_breakdown_inr']['payment_fee'], '33.98')
        self.assertEqual(result['sale_breakdown_inr']['contribution'], '486.27')

    def test_returns_before_and_after_payout(self):
        c = config(); sold = sale(c)
        self.assertEqual(returned(c, sold, after_payout=False), D('-383.983'))
        self.assertEqual(returned(c, sold, after_payout=True), D('-587.881'))

    def test_clawback_recovers_commission(self):
        c = config(post_payout_clawback='yes'); s = sale(c)
        self.assertEqual(returned(c,s,after_payout=True), returned(c,s,after_payout=False))

    def test_unknown_rules_remain_unknown(self):
        report = simulate(config(returned_commission_policy='unknown'))
        self.assertIsNone(report['scenarios'][1]['contribution_inr'])
        self.assertIsNone(report['scenarios'][3]['contribution_inr'])
        self.assertIsNone(report['scenarios'][5]['contribution_inr'])
        self.assertTrue(all(row['campaign_contribution_inr'] is None for row in report['campaign_sensitivity']))

    def test_sequential_and_blocked_coupon(self):
        c = config(stacking_policy='sequential')
        self.assertEqual(sale(c,coupon=True)['net_sales'], D('1529.235'))
        rows=simulate(config(stacking_policy='disallow'))['scenarios']
        self.assertEqual(rows[0]['contribution_inr'], rows[3]['contribution_inr'])

    def test_duplicate_payout_costs_one_extra_commission(self):
        c=config(); s=sale(c); doubled=sale(c,duplicate=True)
        self.assertEqual(s['contribution']-doubled['contribution'], s['commission'])

    def test_exchange_recalculation(self):
        c=config(exchange_commission_rule='recalculate')
        # 1359.15 - 650 - 85 - 90 - 70 - 100 - 90 - 40 - 33.983 - 163.098
        self.assertEqual(exchanged(c,sale(c)), D('37.069'))
        kept=config(exchange_commission_rule='keep_original')
        self.assertEqual(exchanged(kept,sale(kept)), D('-3.731'))

    def test_campaign_weighting_and_fixed_cost(self):
        rows=simulate(config())['campaign_sensitivity']
        self.assertEqual(rows[0]['campaign_contribution_inr'], '157865.60')
        self.assertEqual(rows[2]['campaign_contribution_inr'], '142573.25')

    def test_zero_and_total_returns(self):
        c=config(return_rate_pct='0',stress_return_rate_pct='100')
        rows=simulate(c)['campaign_sensitivity']
        self.assertEqual(rows[0]['campaign_contribution_inr'], '223134.50')
        self.assertEqual(rows[1]['campaign_contribution_inr'], '-211991.50')

    def test_invalid_inputs(self):
        for change in [{'discount_pct':'101'},{'product_cost':'-1'},{'list_price':'NaN'},
                       {'list_price':'Infinity'},{'expected_orders':True},{'expected_orders':0},
                       {'list_price':'1.12345'},{'commission_base':'gross'}]:
            with self.subTest(change=change), self.assertRaises(ValueError): config(**change)

    def test_missing_field(self):
        data=dict(SAMPLE); del data['return_rate_pct']
        with self.assertRaises(ValueError): Campaign.from_dict(data)

    def test_list_price_commission_basis(self):
        self.assertEqual(sale(config(commission_base='list_price'))['commission'], D('239.88'))

    def test_payment_fee_refund(self):
        c=config(payment_fee_refund_pct='100')
        self.assertEqual(returned(c,sale(c),after_payout=False), D('-350'))



if __name__=='__main__': unittest.main()

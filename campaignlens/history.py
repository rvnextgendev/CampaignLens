"""Analyze actual supplied ledger values; do not substitute assumed campaign costs."""
import csv
import io
import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation
from .engine import money

AMOUNTS=['net_sales','refund','product_cost','inventory_recovery','outbound_shipping',
         'packaging','reverse_shipping','handling','payment_fee','commission_paid','commission_recovered']
DATES=['delivered_on','payout_on','returned_on','refund_on']
HEADERS=['brand_id','order_id','status','payment_method',*DATES,*AMOUNTS]


def analyze_csv(text, brand_id):
    if not isinstance(text,str) or len(text.encode())>2_000_000:
        raise ValueError('Historical CSV must be under 2 MB.')
    reader=csv.DictReader(io.StringIO(text))
    if reader.fieldnames!=HEADERS:
        raise ValueError('Use the exact historical_orders.csv template column names and order.')
    orders=[]; seen=set(); total=Decimal(0); after_payout=0
    for line,row in enumerate(reader,2):
        if len(orders)>=10000:
            raise ValueError('CSV is limited to 10,000 orders.')
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'CSV row {line}: incorrect number of columns.')
        if row['brand_id']!=brand_id:
            raise ValueError(f'CSV row {line}: brand_id does not match the selected brand. Upload one brand at a time.')
        oid=row['order_id']
        if not oid or len(oid)>100 or oid in seen:
            raise ValueError(f'CSV row {line}: order_id must be unique and nonempty.')
        seen.add(oid)
        if row['status'] not in ['kept','returned','exchange','rto','partial_refund']:
            raise ValueError(f'CSV row {line}: unsupported status.')
        if row['payment_method'] not in ['prepaid','cod']:
            raise ValueError(f'CSV row {line}: payment_method must be prepaid or cod.')
        amounts={}
        for field in AMOUNTS:
            try: val=Decimal(row[field])
            except (InvalidOperation,ValueError): raise ValueError(f'CSV row {line}: {field} must be numeric.') from None
            if not val.is_finite() or val<0 or val>1_000_000_000 or val.as_tuple().exponent < -4:
                raise ValueError(f'CSV row {line}: invalid {field}.')
            amounts[field]=val
        if amounts['refund']>amounts['net_sales'] or amounts['commission_recovered']>amounts['commission_paid'] or amounts['inventory_recovery']>amounts['product_cost']:
            raise ValueError(f'CSV row {line}: refund or recoveries exceed their original amounts.')
        if row['status']=='kept' and (amounts['refund'] or amounts['inventory_recovery']):
            raise ValueError(f'CSV row {line}: kept orders cannot have refunds or recovered inventory.')
        if row['status'] in ['returned','rto'] and amounts['refund']!=amounts['net_sales']:
            raise ValueError(f'CSV row {line}: full returns/RTO must refund all collected net sales.')
        if row['status']=='partial_refund' and not 0<amounts['refund']<amounts['net_sales']:
            raise ValueError(f'CSV row {line}: partial refund must be between zero and net sales.')
        dates={}
        for field in DATES:
            try: dates[field]=date.fromisoformat(row[field]) if row[field] else None
            except ValueError: raise ValueError(f'CSV row {line}: {field} must be YYYY-MM-DD or blank.') from None
        if row['status']=='rto' and dates['delivered_on']:
            raise ValueError(f'CSV row {line}: RTO cannot have a customer-delivery date.')
        if row['status']!='rto' and not dates['delivered_on']:
            raise ValueError(f'CSV row {line}: delivered_on is required for delivered orders.')
        if row['status'] in ['returned','exchange'] and not dates['returned_on']:
            raise ValueError(f'CSV row {line}: returned_on is required for a return/exchange.')
        for field in ['payout_on','returned_on','refund_on']:
            if dates['delivered_on'] and dates[field] and dates[field]<dates['delivered_on']:
                raise ValueError(f'CSV row {line}: {field} precedes delivery.')
        if amounts['commission_paid']>0 and not dates['payout_on']:
            raise ValueError(f'CSV row {line}: payout_on is required for paid commission.')
        if amounts['refund']>0 and not dates['refund_on']:
            raise ValueError(f'CSV row {line}: refund_on is required for a refund.')
        if dates['returned_on'] and dates['payout_on'] and dates['returned_on']>=dates['payout_on']:
            after_payout+=1
        contribution=(amounts['net_sales']-amounts['refund']-amounts['product_cost']+amounts['inventory_recovery']
                      -sum(amounts[f] for f in ['outbound_shipping','packaging','reverse_shipping','handling','payment_fee','commission_paid'])+amounts['commission_recovered'])
        total+=contribution
        events=[{'date':row[f], 'event':f.removesuffix('_on')} for f in DATES if row[f]]
        events.sort(key=lambda e:(e['date'],e['event']))
        orders.append({'order_id':oid,'status':row['status'],'payment_method':row['payment_method'],
                       'contribution_inr':money(contribution),'ledger_inr':{k:str(v) for k,v in amounts.items()},'events':events,'source_id':f'history:row:{line}'})
    if not orders: raise ValueError('Historical CSV has no orders.')
    delivered=[o for o in orders if o['status']!='rto']
    returns=sum(o['status']=='returned' for o in orders)
    return {'source_sha256':hashlib.sha256(text.encode()).hexdigest(),'orders':orders,'order_count':len(orders),'delivered_count':len(delivered),
            'full_returns':returns,'rto_count':sum(o['status']=='rto' for o in orders),
            'exchange_count':sum(o['status']=='exchange' for o in orders),
            'partial_refund_count':sum(o['status']=='partial_refund' for o in orders),
            'returns_or_exchanges_on_or_after_payout':after_payout,
            'full_return_rate_pct':money(Decimal(returns)*100/len(delivered)) if delivered else None,
            'contribution_inr':money(total),
            'definition':'Actual supplied ledger contribution, before fixed overheads and tax. Return rate denominator is delivered orders. Exchange/RTO/partial refunds counted separately. Uploaded data is not independently verified.'}

"""Versioned brand configuration; new brands are data, not hardcoded UI branches."""
from dataclasses import dataclass, asdict
import re
from .engine import Campaign

CATEGORY_GUIDANCE = {
    'footwear': ['Ask about sizing-related exchanges and worn/damaged returns.', 'Check reverse shipping, replacement shipping and COD/RTO costs.'],
    'boutique_apparel': ['Ask which custom-fit, altered and made-to-order items are eligible for return.', 'Confirm size exchanges, alteration charges and product-condition checks.'],
    'general_retail': ['Confirm return eligibility, product condition and exception handling.'],
}


@dataclass(frozen=True)
class Brand:
    schema_version: int
    brand_id: str
    display_name: str
    category: str
    currency: str
    questions: list[str]
    campaign: dict

    @classmethod
    def parse(cls, data):
        keys = {'schema_version','brand_id','display_name','category','currency','questions','campaign'}
        if not isinstance(data,dict) or set(data)!=keys:
            raise ValueError('Brand configuration must contain exactly: '+', '.join(sorted(keys)))
        if type(data['schema_version']) is not int or data['schema_version']!=1:
            raise ValueError('Unsupported schema_version. Use 1.')
        if not isinstance(data['brand_id'],str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,59}', data['brand_id']):
            raise ValueError('brand_id must be 3–60 lowercase letters, numbers, underscores or hyphens.')
        if data['category'] not in CATEGORY_GUIDANCE:
            raise ValueError('category must be footwear, boutique_apparel or general_retail.')
        if data['currency']!='INR':
            raise ValueError('Version 1 supports INR only; no implicit currency conversion.')
        if not isinstance(data['display_name'],str) or not 1<=len(data['display_name'])<=120:
            raise ValueError('display_name must be 1–120 characters.')
        if not isinstance(data['questions'],list) or len(data['questions'])>20 or any(not isinstance(q,str) or not 1<=len(q)<=500 for q in data['questions']):
            raise ValueError('questions must be up to 20 short strings.')
        campaign=asdict(Campaign.from_dict(data['campaign']))
        if campaign['business_name']!=data['display_name']:
            raise ValueError('campaign.business_name must match display_name.')
        return cls(**{**data,'campaign':campaign})

    def to_dict(self):
        return asdict(self)


def unanswered(c):
    result=[]
    choices={
        'stacking_policy': ('Can an extra coupon stack with the campaign discount?', ['disallow','sequential']),
        'returned_commission_policy': ('What happens to commission on a full return?', ['reverse','retain']),
        'post_payout_clawback': ('Can already-paid commission be recovered?', ['yes','no']),
        'attribution_rule': ('Which rule resolves two affiliates claiming one sale?', ['first_touch','last_touch','manual']),
        'exchange_commission_rule': ('How should commission change after a cheaper exchange?', ['recalculate','keep_original']),
    }
    for field,(question,options) in choices.items():
        if getattr(c,field)=='unknown':
            result.append({'field':field,'question':question,'choices':options})
    return result

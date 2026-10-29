"""Stable source IDs link agent findings to supplied facts and calculations."""
from .engine import Campaign, simulate
from .profiles import unanswered, CATEGORY_GUIDANCE
from decimal import Decimal
import hashlib
import json


def build_bundle(brand, baseline, candidate, notes, policy, history=None):
    if len(notes)>20000 or len(policy)>30000:
        raise ValueError('Notes limited to 20,000 characters; policy to 30,000.')
    if baseline.business_name!=brand.display_name or candidate.business_name!=brand.display_name:
        raise ValueError('Both campaigns must use the selected brand name.')
    before=simulate(baseline); after=simulate(candidate)
    # Projections compare policies/costs at the SAME volume, rate and fixed budget.
    comparison=[]
    for b,a in zip(before['scenarios'],after['scenarios']):
        delta=None if a['contribution_inr'] is None or b['contribution_inr'] is None else str(Decimal(a['contribution_inr'])-Decimal(b['contribution_inr']))
        comparison.append({'scenario':a['scenario'],'baseline_inr':b['contribution_inr'],'candidate_inr':a['contribution_inr'],'delta_inr':delta})
    sources={}
    for label,report in [('baseline',before),('candidate',after)]:
        for field,value in report['inputs'].items(): sources[f'{label}:input:{field}']=value
        for i,row in enumerate(report['scenarios'],1): sources[f'{label}:scenario:{i}']=row
        for i,gap in enumerate(report['policy_gaps'],1): sources[f'{label}:gap:{i}']=gap
    for label,text in [('context',notes),('policy',policy)]:
        for i,line in enumerate(text.splitlines(),1):
            if line.strip(): sources[f'{label}:line:{i}']=line
    if history:
        sources['history:summary']={k:v for k,v in history.items() if k!='orders'}
        # Summaries plus worst 20 rows keep prompts bounded. UI retains all rows.
        for row in sorted(history['orders'],key=lambda r:Decimal(r['contribution_inr']))[:20]:
            sources[row['source_id']]=row
    bundle={'schema_version':1,'brand':{k:v for k,v in brand.to_dict().items() if k!='campaign'},
            'category_questions':CATEGORY_GUIDANCE[brand.category]+brand.questions,
            'baseline':before,'candidate':after,'comparison':comparison,
            'missing_policy_questions':unanswered(candidate),'sources':sources,
            'historical_summary':{k:v for k,v in (history or {}).items() if k!='orders'},
            'historical_comparison':None}
    if history and history['full_return_rate_pct'] is not None:
        bundle['historical_comparison']={
            'configured_return_rate_pct':str(candidate.n('return_rate_pct')),
            'observed_full_return_rate_pct':history['full_return_rate_pct'],
            'difference_percentage_points':str(Decimal(history['full_return_rate_pct'])-candidate.n('return_rate_pct')),
            'note':'Descriptive comparison only; the uploaded cohort may differ from the planned campaign. History does not automatically overwrite inputs.'}
    bundle['snapshot_hash']=hashlib.sha256(json.dumps(bundle,sort_keys=True).encode()).hexdigest()
    return bundle

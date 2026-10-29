"""Offline fixtures exercise orchestration. These are not LLM-generated reviews."""
class DemoProvider:
    async def complete(self,role,bundle):
        mapping={'owner':('candidate:input:minimum_contribution','Confirm the minimum contribution target.'),
                 'finance':('candidate:scenario:3','Review the late-return contribution and recovery assumption.'),
                 'affiliate':('candidate:input:attribution_rule','Confirm how competing affiliate claims are resolved.'),
                 'customer':('candidate:input:stacking_policy','Clarify additional coupon eligibility.'),
                 'operations':('candidate:input:exchange_commission_rule','Document exchange and exception handling.')}
        source,issue=mapping[role]
        return {'summary':f'Offline demonstration of the {role} reviewer. Not a live AI assessment.',
                'findings':[{'issue':issue,'severity':'medium','evidence_ids':[source],
                'impact':'Unclear rules can require manual decisions. This fixture is not a prediction.',
                'suggested_action':'Review the referenced input with the actual brand owner.',
                'question_for_owner':'Is the referenced assumption accurate for this campaign?'}]}

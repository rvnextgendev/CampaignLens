"""CampaignLens — run with python -m streamlit run app.py."""
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from campaignlens.engine import Campaign
from campaignlens.profiles import Brand, unanswered, CATEGORY_GUIDANCE
from campaignlens.history import analyze_csv
from campaignlens.evidence import build_bundle
from campaignlens.agents import run_reviews,GroqProvider,consolidate
from campaignlens.demo import DemoProvider
from campaignlens.store import save_snapshot,list_snapshots,get_snapshot,record_decision,decisions

ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
DB=Path(os.getenv('CAMPAIGNLENS_DB',str(ROOT/'data/reviews.sqlite3')))
st.set_page_config(page_title='CampaignLens',page_icon='🔎',layout='wide')
st.title('CampaignLens')
st.caption('See the impact before you launch · Boutique clothing & footwear · Local review prototype')


def upload_text(file,limit):
    if file.size>limit: raise ValueError(f'Upload must be smaller than {limit} bytes.')
    try:return file.getvalue().decode('utf-8-sig')
    except UnicodeDecodeError: raise ValueError('Use a UTF-8 text file.') from None


def clear_brand_state():
    for key in ['active','saved_id']:
        st.session_state.pop(key,None)


with st.sidebar:
    st.header('Brand workspace')
    selection=st.selectbox('Example brand',['Footwear','Boutique clothing','Custom brand'])
    folder=ROOT/'examples'/('boutique' if selection=='Boutique clothing' else 'footwear')
    if selection=='Custom brand':
        uploaded_profile=st.file_uploader('Upload brand.json',type=['json'])
        if not uploaded_profile:
            st.info('Download an example profile, change its brand_id, name, costs and questions, then upload it here.')
            st.download_button('Brand template',(folder/'brand.json').read_text(),'brand.json','application/json')
            st.stop()
        try:profile_data=json.loads(upload_text(uploaded_profile,100000))
        except ValueError as exc:st.error(str(exc));st.stop()
    else:profile_data=json.loads((folder/'brand.json').read_text())
    try:brand=Brand.parse(profile_data)
    except (ValueError,TypeError) as exc:st.error(f'Invalid brand profile: {exc}');st.stop()
    brand_hash=hashlib.sha256(json.dumps(profile_data,sort_keys=True).encode()).hexdigest()
    if st.session_state.get('brand_hash')!=brand_hash:
        clear_brand_state();st.session_state.brand_hash=brand_hash
    st.write(brand.display_name)
    st.caption(f'{brand.category} · INR, excluding tax')
    api_key=st.text_input('Groq API key (optional)',type='password')
    key=api_key.strip() or os.getenv('GROQ_API_KEY','').strip()
    if not key:
        try:key=st.secrets.get('GROQ_API_KEY','').strip()
        except st.errors.StreamlitSecretNotFoundError:pass
    st.caption('Calculations and offline demo need no key. Live review makes 5 calls, plus provider retries.')
    st.download_button('Download brand profile',json.dumps(brand.to_dict(),indent=2),'brand.json','application/json')
    st.warning('Single-operator local app. Brand selection is not login or access control. Do not deploy publicly with private data.')

st.subheader(brand.display_name)
inputs,analysis,reviews_tab,history_tab=st.tabs(['1. Configure & evidence','2. Compare & calculate','3. Five reviewers','4. Saved decisions'])
with inputs:
    for q in CATEGORY_GUIDANCE[brand.category]+brand.questions:st.write('• '+q)
    col1,col2=st.columns(2)
    with col1:
        st.markdown('**Baseline campaign**')
        baseline_text=st.text_area('Current rules and costs (JSON)',json.dumps(brand.campaign,indent=2),height=360,key=f'baseline_{brand_hash}')
    with col2:
        st.markdown('**Proposed campaign**')
        candidate_text=st.text_area('Proposed rules and costs (JSON)',json.dumps(brand.campaign,indent=2),height=360,key=f'candidate_{brand_hash}')
    try:
        if len(baseline_text)>100000 or len(candidate_text)>100000:raise ValueError('Campaign JSON too large.')
        baseline=Campaign.from_dict(json.loads(baseline_text));candidate_dict=json.loads(candidate_text)
        candidate=Campaign.from_dict(candidate_dict)
    except (ValueError,TypeError) as exc:
        st.error(f'Correct campaign inputs: {exc}');st.stop()
    questions=unanswered(candidate)
    if questions:
        st.markdown('**Missing decisions — answer now or keep unresolved**')
        for item in questions:
            answer=st.selectbox(item['question'],['unknown',*item['choices']],key=f"answer_{brand_hash}_{item['field']}")
            candidate_dict[item['field']]=answer
        candidate=Campaign.from_dict(candidate_dict)
    context_file=st.file_uploader('Business context (.txt or .md)',type=['txt','md'],key=f'context_file_{brand_hash}')
    policy_file=st.file_uploader('Policy document (.txt or .md)',type=['txt','md'],key=f'policy_file_{brand_hash}')
    default_notes='' if selection=='Custom brand' else (folder/'business_context.txt').read_text()
    default_policy='' if selection=='Custom brand' else (folder/'return_policy.md').read_text()
    try:
        source_notes=upload_text(context_file,20000) if context_file else default_notes
        source_policy=upload_text(policy_file,30000) if policy_file else default_policy
    except ValueError as exc:st.error(str(exc));st.stop()
    notes=st.text_area('Goals, assumptions and owner questions',source_notes,height=180,key=f'notes_{brand_hash}_{hashlib.sha256(source_notes.encode()).hexdigest()}')
    policy=st.text_area('Policy evidence',source_policy,height=180,key=f'policy_{brand_hash}_{hashlib.sha256(source_policy.encode()).hexdigest()}')
    historical_file=st.file_uploader('Historical orders CSV (anonymized)',type=['csv'],key=f'csv_{brand_hash}')
    use_demo=st.checkbox('Use fictional sample orders',value=selection!='Custom brand',key=f'demo_history_{brand_hash}')
    st.caption('Use only the exact CSV template; no customer names, addresses or emails. Historical records stay separate from planned inputs.')
    st.download_button('Historical CSV template',(folder/'historical_orders.csv').read_text(),'historical_orders.csv','text/csv')
    hist=None;hist_text=''
    try:
        hist_text=upload_text(historical_file,2000000) if historical_file else ((folder/'historical_orders.csv').read_text() if use_demo and selection!='Custom brand' else '')
        if hist_text:hist=analyze_csv(hist_text,brand.brand_id)
    except ValueError as exc:st.error(str(exc));st.stop()
    current_hash=hashlib.sha256(json.dumps({'brand':brand.to_dict(),'baseline':asdict(baseline),'candidate':asdict(candidate),'notes':notes,'policy':policy,'history':hist_text},sort_keys=True).encode()).hexdigest()
    if st.button('Calculate & compare',type='primary'):
        try:
            bundle=build_bundle(brand,baseline,candidate,notes,policy,hist)
            st.session_state.active={'bundle':bundle,'reviews':[],'coordinator':None,'history':hist,'input_hash':current_hash}
            st.session_state.pop('saved_id',None)
        except ValueError as exc:st.error(str(exc))

active=st.session_state.get('active')
stale=bool(active and active['input_hash']!=current_hash)
if stale:st.warning('Inputs changed. Recalculate before running agents or saving this new version. Existing results belong to the previous inputs.')
with analysis:
    if not active:st.info('Configure your campaign, then click Calculate & compare.')
    else:
        bundle=active['bundle'];report=bundle['candidate']
        a,b,c=st.columns(3)
        a.metric('Normal-sale contribution','₹'+report['sale_breakdown_inr']['contribution'])
        b.metric('Policy questions',len(bundle['missing_policy_questions']))
        c.metric('Uploaded orders',active['history']['order_count'] if active['history'] else 0)
        st.dataframe(bundle['comparison'],width='stretch',hide_index=True)
        st.caption('Per-order contribution differences use each campaign’s configured values; campaign projections below may also differ in volume or budget. Not accounting profit.')
        with st.expander('Campaign projections and assumptions'):
            st.write('Baseline');st.dataframe(bundle['baseline']['campaign_sensitivity'],hide_index=True)
            st.write('Candidate');st.dataframe(report['campaign_sensitivity'],hide_index=True)
            for assumption in report['assumptions']:st.write('• '+assumption)
        for gap in report['policy_gaps']:st.warning(gap)
        if active['history']:
            h=active['history']
            st.subheader('Historical outcomes and event timelines')
            st.write({k:v for k,v in h.items() if k!='orders'})
            st.dataframe([{k:v for k,v in o.items() if k not in ['events','ledger_inr']} for o in h['orders']],width='stretch',hide_index=True)
            selected=st.selectbox('Order timeline',[o['order_id'] for o in h['orders']])
            st.dataframe(next(o['events'] for o in h['orders'] if o['order_id']==selected),hide_index=True)
            if bundle['historical_comparison']:st.json(bundle['historical_comparison'])
        with st.expander('Evidence references available to agents'):
            st.json(bundle['sources'])
        st.download_button('Download calculation snapshot',json.dumps(bundle,indent=2,ensure_ascii=False),'calculation_snapshot.json','application/json')

with reviews_tab:
    if not active:st.info('Calculate the campaign first.')
    else:
        st.caption('Five separate reviews, with up to two running concurrently. Coordinator compilation is deterministic; no debate or majority-vote approval.')
        live=st.button('Run five Groq agents',disabled=stale)
        offline=st.button('Run offline five-role demo',disabled=stale)
        if live or offline:
            if live and not key:st.error('Enter a Groq key, or use the clearly labelled offline demo.')
            else:
                provider=GroqProvider(key) if live else DemoProvider()
                with st.spinner('Running five specialist reviews…'):
                    items=asyncio.run(run_reviews(active['bundle'],provider))
                for item in items:item['source']='groq' if live else 'offline_demo'
                active['reviews']=items;active['coordinator']=consolidate(active['bundle'],items)
                st.session_state.active=active;st.session_state.pop('saved_id',None)
        for item in active['reviews']:
            with st.expander(f"{item['role'].title()} — {item['status']} ({item['source']})",expanded=True):
                if item['status']=='failed':st.error('Review failed or had invalid evidence references. Check key, model access and limits. Other reviews are preserved.')
                else:
                    st.write(item['review']['summary'])
                    for finding in item['review']['findings']:
                        st.markdown('**'+finding['issue']+'**');st.write(finding['impact'])
                        st.write('Suggested action:',finding['suggested_action'])
                        st.write('Owner question:',finding['question_for_owner'])
                        for eid in finding['evidence_ids']:
                            st.caption(eid);st.write(active['bundle']['sources'][eid])
        if active['coordinator']:
            st.subheader('Coordinator compilation')
            st.json(active['coordinator'])
        st.caption('AI roles are simulations. Citation existence is checked; correctness still needs human review. Offline demo output is a test fixture, not AI advice.')
        if st.button('Save immutable review snapshot',disabled=stale):
            st.session_state.saved_id=save_snapshot(DB,brand.brand_id,active)
            st.success('Snapshot saved. Record a decision in Saved decisions.')
        st.download_button('Download complete review',json.dumps({k:v for k,v in active.items() if k not in ['history','input_hash']},indent=2,ensure_ascii=False),'campaign_review.json','application/json')

with history_tab:
    snapshots=list_snapshots(DB,brand.brand_id)
    if not snapshots:st.info('No saved snapshots for this brand yet.')
    else:
        ids=[s['id'] for s in snapshots]
        sid=st.selectbox('Saved snapshot',ids)
        saved=get_snapshot(DB,brand.brand_id,sid)
        st.caption('Snapshot '+sid+' · Reviewer names below are self-reported, not authenticated identities.')
        with st.expander('Saved snapshot contents'):st.json(saved)
        with st.form('record_decision'):
            reviewer=st.text_input('Reviewer name')
            decision=st.selectbox('Decision',['needs_changes','accepted_for_pilot','rejected'])
            reason=st.text_area('Reason and conditions')
            if st.form_submit_button('Record decision'):
                try:
                    record_decision(DB,brand.brand_id,sid,reviewer,decision,reason)
                    st.success('Decision recorded; snapshot unchanged.')
                except ValueError as exc:st.error(str(exc))
        records=decisions(DB,brand.brand_id,sid)
        st.dataframe(records,width='stretch')
        st.download_button('Download decision record',json.dumps({'snapshot':saved,'decisions':records},indent=2,ensure_ascii=False),'decision_record.json','application/json')

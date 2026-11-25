"""Streamlit dashboard for a synthetic IGCAF green-cloud research prototype."""
import io
import json
from dataclasses import asdict
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from simulator import Config, POLICIES, run_experiment, REGIONS

st.set_page_config(page_title='IGCAF | Green Cloud Lab',page_icon='🌱',layout='wide')
st.markdown('''<style>
.block-container {padding-top:1.5rem;max-width:1380px}
.hero {background:linear-gradient(125deg,#102e2c,#15564b);border-radius:18px;color:#f7fff7;padding:24px 28px;margin-bottom:18px}
.hero h1 {font-size:2rem;margin:0;color:#f7fff7}
.hero p {color:#d7f5e9;margin:7px 0 0}
/* Force readable light cards even when Streamlit is in dark mode. */
div[data-testid="stMetric"] {
  background:#edf8f2 !important;
  border:1px solid #b5d8c6 !important;
  border-radius:14px;
  padding:18px 20px;
  min-height:156px;
  box-shadow:0 2px 7px rgba(0,0,0,.08);
}
div[data-testid="stMetric"] [data-testid="stMetricLabel"],
div[data-testid="stMetric"] [data-testid="stMetricLabel"] * {
  color:#25473b !important;
  font-size:1rem !important;
  font-weight:650 !important;
  white-space:normal !important;
  overflow:visible !important;
  text-overflow:clip !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"],
div[data-testid="stMetric"] [data-testid="stMetricValue"] * {
  color:#092e24 !important;
  font-size:clamp(1.4rem,2.2vw,2rem) !important;
  font-weight:750 !important;
  white-space:normal !important;
  overflow:visible !important;
  text-overflow:clip !important;
}
div[data-testid="stMetric"] [data-testid="stMetricDelta"],
div[data-testid="stMetric"] [data-testid="stMetricDelta"] * {
  color:#245c46 !important;
  font-size:.86rem !important;
  white-space:normal !important;
}
</style>''',unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🌱 IGCAF · Green Cloud Lab</h1><p>Integrated Green-Cloud Assessment Framework | Reproducible scheduling & sustainability simulation</p></div>',unsafe_allow_html=True)
st.caption('Research prototype • Synthetic workloads and electricity profiles • No live energy measurements or production deployment claims')
with st.sidebar:
    st.header('⚙️ Scenario settings')
    hours=st.slider('Simulation horizon (hours)',24,72,48,step=12)
    servers=st.slider('Physical servers',9,60,30,step=3)
    jobs=st.slider('Cloud tasks',60,500,260,step=20)
    seed=st.number_input('Reproducible random seed',0,100000,42)
    flex=st.slider('Maximum flexible-task delay (hours)',0,12,5)
    regions=st.checkbox('Allow all three regions',value=True)
    st.divider()
    st.subheader('Synthetic hardware assumptions')
    idle=st.slider('Idle server power (W)',50,180,105)
    peak=st.slider('Peak server power (W)',180,450,260)
    wake=st.slider('Server wake energy (Wh)',0,120,35)
    embodied=st.slider('Embodied allocation (gCO₂e / active server-hour)',0,60,15)
    st.caption('Model constants are illustrative. Adjust them to match experimentally measured hardware.')
    st.divider()
    st.subheader('IGCAF policy weights')
    water=st.slider('Water weight',0.0,0.6,.15,.05)
    cost=st.slider('Cost weight',0.0,0.6,.15,.05)
    delay=st.slider('Delay penalty',0.0,1.0,.20,.05)
cfg=Config(hours=hours,total_servers=servers,tasks=jobs,seed=int(seed),idle_watts=idle,
           peak_watts=peak,wake_kwh=wake/1000,embodied_kg_per_host_hour=embodied/1000,
           max_flex_hours=flex,water_weight=water,cost_weight=cost,
           delay_weight=delay,allow_regions=regions)

@st.cache_data(show_spinner=False)
def calculate(config):
    return run_experiment(config)
with st.spinner('Simulating all four scheduling policies…'):
    tasks,signals,allocs,hourly,summary=calculate(cfg)
base=summary.iloc[0]
igcaf=summary.loc[summary.policy=='Integrated IGCAF'].iloc[0]
reduction=lambda col: (base[col]-igcaf[col])/max(1e-9,base[col])*100
# Two rows give long scientific units enough room and remain legible on laptop screens.
st.subheader('Integrated IGCAF · key results')
m1,m2,m3=st.columns(3)
m1.metric('Facility electricity',f'{igcaf.facility_kwh:.1f} kWh',f'-{reduction("facility_kwh"):.1f}% vs baseline',delta_color='inverse')
m2.metric('Operational carbon',f'{igcaf.operational_kg:.1f} kg CO₂e',f'-{reduction("operational_kg"):.1f}% vs baseline',delta_color='inverse')
m3.metric('Estimated water use',f'{igcaf.water_l:.1f} L',f'-{reduction("water_l"):.1f}% vs baseline',delta_color='inverse')
m4,m5=st.columns(2)
m4.metric('Electricity cost',f'${igcaf.cost_usd:.2f}',f'-{reduction("cost_usd"):.1f}% vs baseline',delta_color='inverse')
m5.metric('Tasks completed on time',f'{igcaf.sla_success_pct:.1f}%',f'{igcaf.sla_violations} missed deadlines',delta_color='off')
st.divider()
t1,t2,t3,t4=st.tabs(['📊 Compare strategies','⏱️ Hourly operations','🧪 Experiment explorer','📚 Methods & export'])
with t1:
    st.subheader('Traditional cloud vs three optimization policies')
    c1,c2=st.columns(2)
    labels={'facility_kwh':'Facility electricity (kWh)','operational_kg':'Operational CO₂e (kg)','water_l':'Water (L)','cost_usd':'Electricity cost (USD)','sci_g_per_completed_task':'SCI-like intensity (gCO₂e/task)','sla_success_pct':'Deadline success (%)'}
    metric=c1.selectbox('Compare by',list(labels),format_func=lambda x:labels[x])
    fig=px.bar(summary,x='policy',y=metric,color='policy',text_auto='.2f',
               color_discrete_sequence=['#75887b','#5a9a86','#48a99b','#187b59'])
    fig.update_layout(showlegend=False,margin=dict(l=5,r=5,t=15,b=15),height=390,xaxis_title='',yaxis_title=labels[metric])
    c1.plotly_chart(fig,use_container_width=True)
    carbon=summary[['policy','operational_kg','embodied_kg']].melt(id_vars='policy',var_name='component',value_name='kg')
    fig2=px.bar(carbon,x='policy',y='kg',color='component',barmode='stack',color_discrete_map={'operational_kg':'#258573','embodied_kg':'#a6ba68'})
    fig2.update_layout(title='Operational vs allocated embodied CO₂e',height=390,xaxis_title='',yaxis_title='kg CO₂e',margin=dict(l=5,r=5,t=40,b=10))
    c2.plotly_chart(fig2,use_container_width=True)
    st.subheader('Full comparative scorecard')
    st.dataframe(summary.rename(columns={'policy':'Policy','facility_kwh':'Energy (kWh)','operational_kg':'Operational CO₂e (kg)','water_l':'Water (L)', 'cost_usd':'Cost (USD)', 'sla_success_pct':'SLA (%)', 'sci_g_per_completed_task':'gCO₂e / completed task'}).round(3),hide_index=True,use_container_width=True)
    if igcaf.sla_success_pct < base.sla_success_pct:
        st.warning('The integrated policy misses more task deadlines than the baseline in this scenario. Compare equal service quality before claiming an improvement.')
with t2:
    st.subheader('Temporal and geographic behaviour')
    selected=st.selectbox('Policy',POLICIES,index=3)
    rows=hourly[hourly.policy==selected]
    aggregate=rows.groupby('hour',as_index=False)[['facility_kwh','operational_kg','active_servers','water_l']].sum()
    a,b=st.columns(2)
    f=px.area(aggregate,x='hour',y='facility_kwh',title='Electricity per simulated hour',color_discrete_sequence=['#247b67'])
    a.plotly_chart(f,use_container_width=True)
    f=px.line(aggregate,x='hour',y='active_servers',title='Active physical servers',markers=True,color_discrete_sequence=['#2a8d77'])
    b.plotly_chart(f,use_container_width=True)
    c,d=st.columns(2)
    regional=rows.pivot(index='region',columns='hour',values='facility_kwh')
    f=px.imshow(regional,color_continuous_scale='YlGn',aspect='auto',title='Regional electricity heatmap (kWh)')
    c.plotly_chart(f,use_container_width=True)
    f=px.line(signals,x='hour',y='carbon_kg_kwh',color='region',title='Assumed region-specific grid carbon intensity (kg/kWh)')
    d.plotly_chart(f,use_container_width=True)
with t3:
    st.subheader('Workload, allocation and deadline analysis')
    x,y=st.columns([1,1])
    x.write('**Generated cloud tasks**')
    x.dataframe(tasks.head(80),hide_index=True,use_container_width=True,height=340)
    selected2=y.selectbox('Examine allocation from',POLICIES,index=3)
    y.write('**Scheduled task decisions**')
    y.dataframe(allocs[selected2].head(80),hide_index=True,use_container_width=True,height=340)
    z1,z2=st.columns(2)
    reg=allocs[selected2].groupby('region').size().reset_index(name='tasks')
    z1.plotly_chart(px.pie(reg,names='region',values='tasks',title='Task placement by region',hole=.55),use_container_width=True)
    hist=allocs[selected2].dropna(subset=['delay_h'])
    z2.plotly_chart(px.histogram(hist,x='delay_h',nbins=15,title='Scheduling delay distribution (hours)'),use_container_width=True)
    st.info('Tasks with no feasible server before the deadline count as SLA violations. They are not secretly completed after the simulation horizon.')
with t4:
    st.subheader('Scientific interpretation')
    st.markdown('''**Functional unit:** one task successfully completed within its deadline. **Boundary:** modeled server IT electricity, facility PUE overhead, operational grid electricity emissions, water intensity, and illustrative amortized hardware emissions. **Baseline:** always-on servers with non-carbon-aware task placement.\n\n**Four evaluated policies:** Traditional (all servers on), Consolidation (pack workloads to enable idle server shutdown), Carbon-aware (select region/time based on carbon intensity), and Integrated IGCAF (combined normalized heuristic plus optional low-utilization power-state reduction).\n\n**Equations:**\n- Facility kWh = IT kWh × region PUE.\n- Operational kgCO₂e = Σ (facility kWh in hour × region-specific kgCO₂e/kWh).\n- Water (L) = Σ (facility kWh × regional L/kWh).\n- Allocated embodied kgCO₂e = active server-hours × specified embodied kg/server-hour.\n- SCI-like (gCO₂e/task) = 1000 × (operational + allocated embodied emissions) / successful tasks.\n\n**Limitations:** Discrete one-hour scheduling, stylized server power curve and optional power-state factor; no measured physical CPU frequency, no actual rack cooling, network traffic or data replication energy, no external carbon-intensity API, no queuing within hour, and no hardware life-cycle inventory. Therefore this is **not an independently compliant SCI audit or proof of real-world energy savings**. The embodied factor is particularly illustrative. Comparison policies have equal input tasks and server fleet but may have different successful task counts.''')
    st.markdown('**Research connections:** IGCAF stages A–E (define baseline, collect indicators, apply interventions, optimize multiple objectives, validate against counterfactual policies).')
    st.markdown('References: [Green Software Foundation SCI specification](https://sci.greensoftware.foundation/) · [Streamlit documentation](https://docs.streamlit.io/)')
    left,right,third=st.columns(3)
    left.download_button('⬇️ Download policy metrics CSV',summary.to_csv(index=False),file_name='igcaf_policy_metrics.csv',mime='text/csv')
    right.download_button('⬇️ Download hourly results CSV',hourly.to_csv(index=False),file_name='igcaf_hourly_results.csv',mime='text/csv')
    report={'project':'IGCAF green cloud simulation','disclaimer':'Synthetic model, not field-measured results','config':asdict(cfg),'metrics':summary.to_dict('records')}
    third.download_button('⬇️ Download study JSON',json.dumps(report,indent=2),file_name='igcaf_experiment.json',mime='application/json')
st.caption('IGCAF · Research demonstration | All energy, electricity mix, water and cost factors are scenario assumptions, not provider-specific observed data.')

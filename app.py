import json
import requests
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

st.set_page_config(page_title='BTC LIVE | 10s',layout='wide',initial_sidebar_state='collapsed')
st.markdown('''<style>#MainMenu,header,footer,[data-testid="stToolbar"],[data-testid="stSidebar"]{display:none!important}.block-container{padding:0!important;max-width:100%!important}[data-testid="stAppViewContainer"]{background:#070b0e}iframe{display:block}</style>''',unsafe_allow_html=True)
@st.cache_data(ttl=60)
def bootstrap():
    r=requests.get('https://api.exchange.coinbase.com/products/BTC-USD/candles',params={'granularity':60},headers={'User-Agent':'BTC15-Research/1.0'},timeout=12)
    r.raise_for_status()
    return sorted([{'time':int(x[0]),'open':float(x[3]),'high':float(x[2]),'low':float(x[1]),'close':float(x[4]),'volume':float(x[5])} for x in r.json()],key=lambda x:x['time'])[-250:]
try:
    history=bootstrap()
    template=Path(__file__).with_name('terminal.html').read_text()
    components.html(template.replace('__HISTORY__',json.dumps(history)),height=980,scrolling=False)
except Exception as e:
    st.error(f'Could not initialize live chart: {type(e).__name__}: {e}')

import pandas as pd
from structure_overlay import overlays

def test_empty():
    assert overlays(pd.DataFrame())=={'zones':[],'fvgs':[],'markers':[]}

def test_constant_prices_no_fvg_or_signal():
    ts=pd.date_range('2026-01-01',periods=80,freq='min',tz='UTC')
    df=pd.DataFrame({'ts':ts,'open':[100]*80,'high':[101]*80,'low':[99]*80,'close':[100]*80,'volume':[1]*80})
    o=overlays(df)
    assert o['fvgs']==[] and o['markers']==[]

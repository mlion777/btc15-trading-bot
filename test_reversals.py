import pandas as pd
from reversals import reversal_setup

def make_bars():
    close=[100+i*.08 for i in range(45)]
    return pd.DataFrame({'ts':pd.date_range('2026-01-01',periods=45,freq='min',tz='UTC'),
                         'open':[v-.05 for v in close], 'high':[v+.2 for v in close],
                         'low':[v-.2 for v in close], 'close':close,'volume':[100]*45})

def test_no_future_leakage():
    x=make_bars()
    r=reversal_setup(x,'DOWN')
    y=pd.concat([x,pd.DataFrame([{'ts':x.ts.iloc[-1]+pd.Timedelta(minutes=1),'open':90,'high':91,'low':80,'close':81,'volume':100}])],ignore_index=True)
    assert r==reversal_setup(y.iloc[:-1],'DOWN')

def test_trend_without_reversal_not_confirmed():
    assert not reversal_setup(make_bars(),'DOWN')['confirmed']

def test_insufficient_data():
    assert reversal_setup(make_bars().head(10),'UP')['stage']=='UNAVAILABLE'

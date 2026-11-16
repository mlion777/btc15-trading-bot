import pandas as pd
from confirmations import confirm_setup, trade_pressure

def test_no_candles():
    assert not confirm_setup(None,'UP')['ok']

def test_flat_market_rejected():
    x=pd.DataFrame({'ts':pd.date_range('2026-01-01',periods=100,freq='min',tz='UTC'),'open':[100.]*100,'high':[101.]*100,'low':[99.]*100,'close':[100.]*100,'volume':[10.]*100})
    assert not confirm_setup(x,'UP')['ok']
    assert not confirm_setup(x,'DOWN')['ok']

def test_aggressor_side():
    ts=pd.Timestamp('2026-01-01',tz='UTC')
    p=trade_pressure([{'ts':ts,'price':100,'size':2,'side':'sell'},{'ts':ts,'price':100,'size':1,'side':'buy'}])
    assert abs(p['imbalance']-1/3)<1e-9

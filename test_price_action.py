import pandas as pd
from price_action import analyze

def candles(values):
    return pd.DataFrame({'ts':pd.date_range('2026-01-01',periods=len(values),freq='min',tz='UTC'),'open':values,'close':values,'high':[v+.05 for v in values],'low':[v-.05 for v in values]})

def test_bullish_progression():
    r=analyze(candles([100,101,102,103,104,105,106,107,108,109,110,109.8]),{'reference':105},109.8)
    assert r['side']=='UP' and r['votes']['UP']>=3

def test_bearish_progression():
    r=analyze(candles([110,109,108,107,106,105,104,103,102,101,100,100.2]),{'reference':105},100.2)
    assert r['side']=='DOWN' and r['votes']['DOWN']>=3

def test_no_data():
    assert analyze(None)['side'] is None

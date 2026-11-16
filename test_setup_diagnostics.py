from setup_diagnostics import describe_setup,entry_diagnostics

def test_bullish_developing_visible_without_entry():
    x=describe_setup({'ema9':102,'ema21':100,'macd_histogram':1,'rsi14':60},{'ok':False})
    assert x['bias']=='LONG' and x['stage']=='DEVELOPING SETUP'

def test_bearish_developing_visible_without_entry():
    x=describe_setup({'ema9':98,'ema21':100,'macd_histogram':-1,'rsi14':39},{'ok':False})
    assert x['bias']=='SHORT'

def test_reasons_not_hidden():
    r=entry_diagnostics({'side':None,'reason':'Spread too wide'},{'ok':False,'reason':'stale'},None,None,None,None,None)
    assert any('stale' in x for x in r) and any('Spread' in x for x in r)

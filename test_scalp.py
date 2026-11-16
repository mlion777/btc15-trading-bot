from scalp import scalp_screen

def test_no_entry_without_data():
    assert scalp_screen({},None,None,None,{'ok':False})['side'] is None

def test_paper_up_with_confirmation():
    z={'ema9':101,'ema21':100,'macd_histogram':2,'rsi14':61,'spot':102}
    m={'reference':100,'seconds_left':450,'active':True,'accepting_orders':True}
    ob={'fillable':True,'vwap':.52,'spread':.02}
    r=scalp_screen(z,m,ob,ob,{'ok':True})
    assert r['side']=='UP' and r['exit_target']>r['entry']

def test_no_entry_if_expensive():
    z={'ema9':101,'ema21':100,'macd_histogram':2,'rsi14':61,'spot':102}
    m={'reference':100,'seconds_left':450,'active':True,'accepting_orders':True}
    ob={'fillable':True,'vwap':.96,'spread':.02}
    assert scalp_screen(z,m,ob,ob,{'ok':True})['side'] is None

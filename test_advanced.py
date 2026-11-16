import sqlite3
import unittest
import numpy as np
import pandas as pd
from advanced import detailed_book, research_backtest, init_research_db, record_trade, settle_trade, get_metadata_reference, expected_calibration_error
from unittest.mock import patch

class Tests(unittest.TestCase):
    def test_metadata(self):
        self.assertEqual(get_metadata_reference({'eventMetadata':{'priceToBeat':'75000'},'markets':[]})[0],75000)
        self.assertEqual(get_metadata_reference({'markets':[]})[2],'UNAVAILABLE')
    def test_book_vwap(self):
        raw={'asks':[{'price':'0.6','size':'10'},{'price':'0.5','size':'10'}], 'bids':[{'price':'0.4','size':'4'}]}
        with patch('advanced.get',return_value=raw):
            book=detailed_book('token',8)
        self.assertAlmostEqual(book['ask'],.5)
        self.assertTrue(book['fillable'])
        self.assertAlmostEqual(book['shares'],10+3/.6)
        self.assertAlmostEqual(book['vwap'],8/15)
    def test_db(self):
        con=init_research_db(':memory:')
        m={'slug':'test','seconds_left':500,'reference_grade':'SOURCE_REPORTED'}
        ob={'fillable':True,'vwap':.5,'shares':20}
        record_trade(con,m,'UP',ob,10,.01)
        settle_trade(con,1,'UP','verified externally')
        self.assertAlmostEqual(con.execute('select pnl from trades').fetchone()[0],9.9)
        con.close()
    def test_backtest(self):
        rng=np.random.default_rng(4)
        n=6000
        ts=pd.date_range('2026-01-01',periods=n,freq='min',tz='UTC')
        close=70000*np.exp(np.cumsum(rng.normal(0,.0004,n)))
        df=pd.DataFrame({'ts':ts,'open':close,'high':close*1.0001,'low':close*.9999,'close':close,'volume':100.})
        result,error=research_backtest(df)
        self.assertIsNone(error)
        self.assertTrue(0<=result['metrics']['holdout_brier']<=1)
        self.assertTrue(result['metrics']['holdout_windows']>30)
    def test_ece(self):
        self.assertAlmostEqual(expected_calibration_error([1,0],[.5,.5]),0)
if __name__=='__main__':unittest.main()

import unittest
import pandas as pd
from microstructure import pressure, provisional_candles, supply_demand_zones
class Tests(unittest.TestCase):
    def test_pressure(self):
        p=pressure({'bids':[(.5,100)],'asks':[(.6,50)]})
        self.assertAlmostEqual(p['bid_share'],50/80)
    def test_candle(self):
        trades=[{'id':1,'ts':pd.Timestamp('2026-01-01T00:00:01Z'),'price':100,'size':1}, {'id':2,'ts':pd.Timestamp('2026-01-01T00:00:05Z'),'price':101,'size':2}]
        x=provisional_candles(trades)
        self.assertEqual(x.close.iloc[0],101)
        self.assertEqual(x.volume.iloc[0],3)
    def test_zones_empty(self):
        self.assertEqual(supply_demand_zones(pd.DataFrame()),{'demand':[],'supply':[]})
if __name__=='__main__':unittest.main()

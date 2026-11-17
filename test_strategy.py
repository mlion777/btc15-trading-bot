import unittest
import pandas as pd
from strategy import resample,technical,consensus,zones
class Test(unittest.TestCase):
 def setUp(self):
  t=pd.date_range('2026-01-01',periods=200,freq='min',tz='UTC')
  self.d=pd.DataFrame({'ts':t,'open':[100+i*.1 for i in range(200)],'close':[100.07+i*.1 for i in range(200)],'high':[100.12+i*.1 for i in range(200)],'low':[99.97+i*.1 for i in range(200)],'volume':[10]*200})
 def test_resample(self):self.assertEqual(len(resample(self.d,300)),40)
 def test_up(self):self.assertEqual(technical(self.d)['side'],'UP')
 def test_insufficient(self):self.assertEqual(technical(self.d.head(3))['side'],'WAIT')
 def test_zones(self):self.assertIsInstance(zones(self.d),list)
 def test_consensus(self):
  frames={'1m':self.d,'5m':resample(self.d,300),'15s':self.d,'30s':self.d}
  self.assertEqual(consensus(frames)[0],'UP')
if __name__=='__main__':unittest.main()

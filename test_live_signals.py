import unittest
from live_signals import technical_signal
class SignalTests(unittest.TestCase):
 def test_missing_data_waits(self):
  self.assertEqual(technical_signal(None,{},None,None,None,{} )['bias'],'WAIT')
 def test_missing_reference_waits(self):
  self.assertEqual(technical_signal(None,{'spot':100},{'seconds_left':300,'reference':None},{},{},{'ok':True})['bias'],'WAIT')
if __name__=='__main__':unittest.main()

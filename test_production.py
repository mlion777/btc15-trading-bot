import unittest, time
from datetime import datetime,timezone
from production import open_db,capture,summary,evidence_outcome,audit_observations,quote_integrity,signal_gate

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.now=time.time()
        self.con=open_db(':memory:')
        self.market={'slug':'btc-updown-15m-'+str(int(self.now//900)*900),'start':int(self.now//900)*900,'end':int(self.now//900)*900+900,'reference':75000.,'reference_grade':'SOURCE_REPORTED','active':True,'accepting_orders':True}
        self.book={'ask':.55,'bid':.53,'fillable':True,'shares':18.18,'vwap':.55,'spread':.02,'ask_depth_usd':100.,'observed_at':datetime.fromtimestamp(self.now,timezone.utc).isoformat()}
        self.quality={'ok':True,'age_seconds':65,'gaps':0}
    def tearDown(self):self.con.close()
    def test_quote_integrity(self):
        self.assertTrue(quote_integrity(self.book,self.book,self.now)[0])
        bad={**self.book,'bid':.57}
        self.assertFalse(quote_integrity(bad,self.book,self.now)[0])
    def test_capture(self):
        out=capture(self.con,self.market,75001,'spot proxy',self.quality,self.book,self.book,self.now)
        self.assertTrue(out['ok'])
        self.assertEqual(summary(self.con)['observations'],1)
    def test_attested_outcome_never_verified(self):
        capture(self.con,self.market,75001,'spot proxy',self.quality,self.book,self.book,self.now)
        evidence_outcome(self.con,self.market['slug'],'UP','https://polymarket.com/event/example')
        a=audit_observations(self.con)
        self.assertEqual(a.iloc[0].verification_level,'USER_ATTESTED')
    def test_signal_fail_closed(self):
        result=signal_gate(self.market,self.quality,self.book,self.book,prob_up=.99,model_validated=True,now=self.now)
        self.assertEqual(result['side'],'WAIT')
        self.assertIn('Oracle reference not independently verified',result['reasons'])
    def test_missing_probability(self):
        result=signal_gate(self.market,self.quality,self.book,self.book,prob_up=None,model_validated=False,now=self.now)
        self.assertEqual(result['side'],'WAIT')
if __name__=='__main__':unittest.main()

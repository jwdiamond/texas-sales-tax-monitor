"""Offline sanity tests for CPI importer and real growth formulas."""
import unittest
from fetch_cpi import parse
class CPITests(unittest.TestCase):
 def test_formula(self):
  nominal=.06; inflation=.03
  self.assertAlmostEqual(100*((1+nominal)/(1+inflation)-1),2.9126213592)
 def test_missing_cpi_not_interpolated(self):
  # A missing CPI month must remain unavailable rather than extrapolated.
  cpi={'2025-09':320.,'2026-09':330.}
  self.assertNotIn('2026-10',cpi)
 def test_parser_rejects_sparse(self):
  with self.assertRaises(ValueError):parse('observation_date,CPIAUCNS\n2026-09-01,336.940\n')
 def test_parser_rejects_duplicate(self):
  csv='observation_date,CPIAUCNS\n'+'\n'.join(f'{year}-{month:02d}-01,250' for year in range(2000,2026) for month in range(1,13))+'\n2025-12-01,250\n'
  with self.assertRaises(ValueError):parse(csv)
 def test_parser_valid_history(self):
  csv='observation_date,CPIAUCNS\n'+'\n'.join(f'{year}-{month:02d}-01,250' for year in range(2000,2026) for month in range(1,13))+'\n'
  data,n,last=parse(csv)
  self.assertEqual(n,312)
  self.assertEqual(last,'2025-12')
  self.assertIn(b'2000-01,250.000',data)
if __name__=='__main__':unittest.main()

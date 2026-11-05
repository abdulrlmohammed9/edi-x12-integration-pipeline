import json
from pathlib import Path
import tempfile
import unittest
from edi_pipeline.core import parse, ValidationError
from edi_pipeline.__main__ import run

ROOT = Path(__file__).resolve().parents[1]
def sample(kind):
    return (ROOT/f'samples/valid/{kind}.edi').read_text()

class PipelineTests(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(parse(sample('204'))['stops'],[{'sequence':'1','reason':'LD'},{'sequence':'2','reason':'UL'}])
        self.assertEqual(parse(sample('210'))['amount'],'1250.50')
        self.assertEqual(parse(sample('214'))['status'],'in_transit')
    def test_invalid_fixtures(self):
        for path in (ROOT/'samples/invalid').glob('*.edi'):
            with self.subTest(path=path.name), self.assertRaises(ValidationError):
                parse(path.read_text())
    def test_missing_segment(self):
        with self.assertRaises(ValidationError):
            parse(sample('214').replace('B10*','ZZZ*'))
    def test_date(self):
        with self.assertRaises(ValidationError):
            parse(sample('214').replace('20261105*0930','20261305*0930'))
    def test_amount(self):
        with self.assertRaises(ValidationError):
            parse(sample('210').replace('125050','-125050'))
    def test_custom_delimiters(self):
        self.assertEqual(parse(sample('214').replace('*','|').replace('~','!'))['shipment_id'],'LOAD1001')
    def test_empty_and_truncated(self):
        for text in ['', 'ISA*00~',sample('214')[:150]]:
            with self.subTest(text=text),self.assertRaises(ValidationError):
                parse(text)
    def test_replay_and_quarantine(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'output'
            first=run(ROOT/'samples',out)
            self.assertEqual(dict(first),dict(accepted=3,rejected=3,duplicate=0))
            second=run(ROOT/'samples',out)
            self.assertEqual(second['duplicate'],6)
            self.assertEqual(len(list((out/'accepted').glob('*.json'))),3)
            self.assertEqual(len(list((out/'quarantine').glob('*.edi'))),3)
            self.assertIn('X12 Integration Monitor',(out/'dashboard.html').read_text())
            self.assertEqual(json.loads((out/'summary.json').read_text())['cumulative_unique_files']['rejected'],3)
    def test_production_and_multi_transaction_rejected(self):
        for text in [sample('214').replace('*T*:', '*P*:'),sample('214')+sample('214')]:
            with self.assertRaises(ValidationError):
                parse(text)
    def test_total_mismatch(self):
        with self.assertRaises(ValidationError):
            parse(sample('210').replace('L3*1000*G***125050','L3*1000*G***123'))

if __name__=='__main__':
    unittest.main()

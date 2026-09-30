from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from trace_evidence import TraceEvidence
from capture import OUT
from audit import Bound

class TraceTests(unittest.TestCase):
    def test_only_evidenced_root_event_is_reconstructed(self):
        bound=Bound();packet=bound.gz('unguarded/batch_02062.input.json.gz')['packet'];expected=bound.gz('unguarded/batch_02062.output.json.gz')[1]
        request={**packet['Accounts'][1],'NowNS':packet['NowNS'],'Responses':packet['Responses']}
        actual=json.loads((OUT/'trace_2062/reused_process_00.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            evidence=TraceEvidence(Path(directory));evidence.verify(actual,expected,request,'unguarded',2062,'quote_aware_fee30','candidate')
            self.assertEqual(len(evidence.records),1)
            for label,change in [
                ('cash',lambda a:a['State'].update(Cash='495')),
                ('missing_engine_request',lambda a:a['Paths'].remove('/prediction')),
                ('extra_engine_request',lambda a:a['Paths'].append('/markets')),
                ('other_unknown_request',lambda a:a['Paths'].append('/unexplained'))]:
                bad=deepcopy(actual);change(bad)
                with self.subTest(case=label),self.assertRaises(AssertionError):evidence.verify(bad,expected,request,'unguarded',2062,'quote_aware_fee30','candidate')
            with self.assertRaises(AssertionError):evidence.verify(actual,expected,request,'unguarded',2063,'quote_aware_fee30','candidate')

if __name__=='__main__':unittest.main()

"""Keep shipped queue illustrations tied to actual matching outputs."""
import json
import unittest
from pathlib import Path

from project_tools.export_event_demo import produce


class QueueEvidenceTests(unittest.TestCase):
    def test_shipped_evidence_matches_owner_and_preserves_integer_clocks(self):
        path = Path(__file__).resolve().parents[1] / 'web/src/data/queue-demo.json'
        data = json.loads(path.read_text())
        self.assertEqual(data, produce())
        for case in data['cases'].values():
            for event in case['events']:
                self.assertIsInstance(event['effective_ns'], str)
        own = lambda c: sum(int(f['volume']) for e in data['cases'][c]['events']
                            for f in e['fills'] if f['buy_id']=='own')
        self.assertEqual(own('timely'), 2)
        self.assertEqual(own('late'), 0)
        self.assertEqual(own('cancel-fast'), 0)
        self.assertEqual(own('cancel-late'), 3)

if __name__ == '__main__':
    unittest.main()

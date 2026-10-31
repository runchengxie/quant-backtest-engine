import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

FIXTURES = Path(__file__).parent / 'fixtures'

class ClientTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.executable = Path(self.directory.name) / 'engine'

    def client(self, result):
        from quant_backtest_engine import EngineClient
        output = result if isinstance(result, str) else json.dumps(result)
        self.executable.write_text('#!/usr/bin/env python3\nprint(' + repr(output) + ')\n')
        self.executable.chmod(0o700)
        return EngineClient(self.executable, hashlib.sha256(self.executable.read_bytes()).hexdigest())

    def fixture(self, name):
        return json.loads((FIXTURES / (name + '.json')).read_text())

    def test_returns_validated_wire_dictionaries(self):
        for request, result, method in [('sessions', 'session-result', 'run_sessions'), ('sizing', 'sizing-result', 'size')]:
            expected = self.fixture(result)
            self.assertEqual(getattr(self.client(expected), method)(self.fixture(request)), expected)

    def test_rejects_corrupt_evidence(self):
        from quant_backtest_engine import EngineProtocolError
        changes = [lambda r: r.update(final_cash='1'), lambda r: r['daily_positions'][0].update(mark_price='12'), lambda r: r['fills'][0].update(ts_ns=0), lambda r: r['orders'][0].update(status='OPEN'), lambda r: r.update(extra=True), lambda r: r['daily_ledger'][0].update(commission='0')]
        for change in changes:
            result = self.fixture('session-result')
            change(result)
            with self.subTest(result=result), self.assertRaises(EngineProtocolError):
                self.client(result).run_sessions(self.fixture('sessions'))

    def test_rejects_duplicate_and_nonfinite_json(self):
        from quant_backtest_engine import EngineProtocolError
        for result in ['{"schema_version":"a","schema_version":"b"}', '{"x":NaN}']:
            with self.assertRaises(EngineProtocolError):
                self.client(result).size(self.fixture('sizing'))

    def test_rejects_t1_round_trip_even_when_balances_reconcile(self):
        from quant_backtest_engine import EngineProtocolError
        result = self.fixture('same-day-result')
        result['enforce_t1'] = True
        with self.assertRaisesRegex(EngineProtocolError, r'T\+1'):
            self.client(result).run_sessions(self.fixture('sessions'))

    def test_timeout_and_process_errors(self):
        from quant_backtest_engine import EngineClient, EngineProtocolError
        for body in ['import time; time.sleep(1)', 'raise SystemExit(7)']:
            self.executable.write_text('#!/usr/bin/env python3\n' + body + '\n')
            self.executable.chmod(0o700)
            client = EngineClient(self.executable, hashlib.sha256(self.executable.read_bytes()).hexdigest(), timeout=0.05)
            with self.assertRaises(EngineProtocolError):
                client.size(self.fixture('sizing'))

    def test_rejects_inconsistent_sizing(self):
        from quant_backtest_engine import EngineProtocolError
        for mutate in [lambda r: r['targets'][0].update(planned_quantity='0'),
                       lambda r: r['orders'][0].update(information_ts_ns=0),
                       lambda r: r['orders'][0].update(quantity='0'),
                       lambda r: r.update(currency='USD')]:
            result = self.fixture('sizing-result')
            mutate(result)
            with self.assertRaises(EngineProtocolError):
                self.client(result).size(self.fixture('sizing'))

    def test_constructor_rejects_unpinned_selection(self):
        from quant_backtest_engine import EngineClient
        for binary, digest, timeout in [(Path('relative'), 'a' * 64, 30),
                                        (self.executable, 'A' * 64, 30),
                                        (self.executable, 'a' * 64, float('inf')),
                                        (self.executable, 'a' * 64, 0)]:
            with self.assertRaises(ValueError):
                EngineClient(binary, digest, timeout=timeout)

    def test_digest_mismatch(self):
        from quant_backtest_engine import EngineProtocolError
        client = self.client(self.fixture('sizing-result'))
        self.executable.write_text('changed')
        with self.assertRaises(EngineProtocolError):
            client.size(self.fixture('sizing'))

    @unittest.skipUnless(os.environ.get('QUANT_ENGINE_BINARY'), 'select real binary explicitly')
    def test_real_binary(self):
        from quant_backtest_engine import EngineClient
        binary = Path(os.environ['QUANT_ENGINE_BINARY']).resolve()
        client = EngineClient(binary, hashlib.sha256(binary.read_bytes()).hexdigest())
        self.assertEqual(client.run_sessions(self.fixture('sessions')), self.fixture('session-result'))
        self.assertEqual(client.size(self.fixture('sizing')), self.fixture('sizing-result'))

if __name__ == '__main__':
    unittest.main()

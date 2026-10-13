import json, unittest
from hourly_sidecar import daily_body, hourly_body, ridge_body

ST = dict(schema='rotation-hourly-forecast-state-v1', live_enabled=False, pairs=['AUSDT', 'BUSDT'], issued_hour=497760,
          smoothed_scores=[.2, -.2], raw_scores=[1., -1.], observations=5, daily=[dict(issued_hour=497736, scores=[-.5, .5])])
UP = dict(available=True, mode='research_rank_forecast', venue='POLONIEX', issued_at='2026-10-13T00:00:00Z', execution_hour='2026-10-13T01:00:00Z',
          rank_scores={'AUSDT': .9, 'BUSDT': .1})


class T(unittest.TestCase):
    def test_daily_uses_snapshot_of_same_issue(self):
        d = daily_body(json.dumps(UP), ST); self.assertEqual(d['rank_scores'], {'AUSDT': -.5, 'BUSDT': .5}); self.assertEqual(d['execution_hour'], UP['execution_hour'])
        with self.assertRaises(ValueError): daily_body(json.dumps({**UP, 'issued_at': '2026-10-12T00:00:00Z'}), ST)

    def test_hourly_fresh_or_stale(self):
        h = hourly_body(ST, 497760*3600+600); self.assertEqual(h['cadence'], 'hourly'); self.assertEqual(h['issued_at'], h['execution_hour'])
        hourly_body(ST, 497761*3600+3000)
        with self.assertRaises(ValueError): hourly_body(ST, 497762*3600+1)


class R(unittest.TestCase):
    def test_ridge_serves_previous_hour_with_one_hour_delay(self):
        st = dict(schema='rotation-ridge-forecast-state-v1', live_enabled=False, pairs=['AUSDT', 'BUSDT'],
                  issues=[dict(issued_hour=497759, edges=[.01, -.01]), dict(issued_hour=497760, edges=[.02, -.02])])
        r = ridge_body(st, 497760*3600+300); self.assertEqual(r['rank_scores'], {'AUSDT': .01, 'BUSDT': -.01})
        self.assertEqual((r['issued_at'], r['execution_hour']), ('2026-10-13T23:00:00Z', '2026-10-14T00:00:00Z'))
        with self.assertRaises(ValueError): ridge_body(st, 497762*3600)


if __name__ == '__main__': unittest.main()

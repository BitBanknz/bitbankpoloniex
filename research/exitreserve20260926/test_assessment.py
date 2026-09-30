from decimal import Decimal as D
import random
import unittest
from assessment import drawdowns,quantile
from checks_v2 import DAY,ns,iso


class AssessmentTests(unittest.TestCase):
    def test_calendar_boundary_and_initial_budget(self):
        values=[(1,D(100)),(27*DAY+1,D(80)),(28*DAY+1,D(70)),(29*DAY+1,D(50))]
        actual=drawdowns(values,D(100))
        self.assertEqual(D(actual['full_drawdown_pct']),D(50))
        self.assertEqual(D(actual['rolling_28d_drawdown_pct']),D('37.5'))
        self.assertEqual(D(drawdowns([(1,D(90))],D(100))['full_drawdown_pct']),D(10))

    def test_drawdown_matches_direct_every_pair_reference(self):
        rng=random.Random(20260926)
        for _ in range(100):
            points=[];at=1
            for _ in range(50):
                at+=rng.randint(1,3)*DAY;points.append((at,D(rng.randint(50,150))))
            all_points=[(points[0][0],D(100)),*points]
            full=max(D(0),max((v-w)/v*100 for i,(_,v) in enumerate(all_points) for _,w in all_points[i:]))
            rolling=max(D(0),max((v-w)/v*100 for i,(t,v) in enumerate(all_points)
                                 for u,w in all_points[i:] if u-t<=28*DAY))
            actual=drawdowns(points,D(100))
            self.assertEqual(D(actual['full_drawdown_pct']),full)
            self.assertEqual(D(actual['rolling_28d_drawdown_pct']),rolling)

    def test_invalid_marks_and_quantiles(self):
        for points in ([],[(1,D(0))],[(1,D('NaN'))],[(1,D(100)),(1,D(101))]):
            with self.assertRaises(ValueError):drawdowns(points)
        self.assertEqual(quantile([D(0),D(10)],D('.1')),D(1))

    def test_canonical_clocks_keep_nanoseconds(self):
        for value in (1790211645000000000,1790211645000000001,1790211645123400000):
            self.assertEqual(ns(iso(value)),value)
        self.assertEqual(iso(1790211645000000000),'2026-09-24T01:00:45Z')


if __name__=='__main__':unittest.main()

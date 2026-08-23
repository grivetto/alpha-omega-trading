#!/usr/bin/env python3
"""Test ResourceSupervisor: soglie, backpressure, zero OOM."""
import unittest

from denaro.application.supervisor import NodeMetrics, ResourceSupervisor


class TestResourceSupervisor(unittest.TestCase):
    def test_nominal(self):
        s = ResourceSupervisor()
        m = NodeMetrics(rss_mb=100.0, cpu_pct=5.0, ram_total_mb=4000.0)
        st = s.check(m)
        self.assertEqual(st.level, "nominal")
        self.assertTrue(st.can_start_worker)
        self.assertEqual(st.tick_factor, 1.0)
        self.assertEqual(s.adjusted_interval(60.0, m), 60.0)

    def test_ram_critical_blocca(self):
        s = ResourceSupervisor(ram_critical_pct=0.85)
        m = NodeMetrics(rss_mb=3600.0, cpu_pct=5.0, ram_total_mb=4000.0)  # 90%
        st = s.check(m)
        self.assertEqual(st.level, "critical")
        self.assertFalse(st.can_start_worker)
        self.assertEqual(st.tick_factor, s.tick_max_factor)

    def test_cpu_critical_blocca(self):
        s = ResourceSupervisor(cpu_critical_pct=0.90)
        m = NodeMetrics(rss_mb=100.0, cpu_pct=95.0, ram_total_mb=4000.0)  # 95% CPU
        st = s.check(m)
        self.assertEqual(st.level, "critical")
        self.assertFalse(st.can_start_worker)

    def test_ram_throttle_rallenta_progressivamente(self):
        s = ResourceSupervisor(ram_throttle_pct=0.70, ram_critical_pct=0.85,
                               tick_max_factor=5.0)
        # 75%: tra throttle (70%) e critical (85%) → fattore > 1
        m = NodeMetrics(rss_mb=3000.0, cpu_pct=5.0, ram_total_mb=4000.0)
        st = s.check(m)
        self.assertEqual(st.level, "throttled")
        self.assertTrue(st.can_start_worker)
        self.assertGreater(st.tick_factor, 1.0)
        self.assertLess(st.tick_factor, 5.0)
        # il tick rallenta
        self.assertGreater(s.adjusted_interval(60.0, m), 60.0)

    def test_throttle_a_ram_alta_fattore_max(self):
        s = ResourceSupervisor(ram_throttle_pct=0.70, ram_critical_pct=0.85,
                               tick_max_factor=5.0)
        m = NodeMetrics(rss_mb=3398.0, cpu_pct=5.0, ram_total_mb=4000.0)  # 84.95%
        st = s.check(m)
        self.assertAlmostEqual(st.tick_factor, 5.0, places=1)

    def test_ram_0_da_metriche_di_default(self):
        s = ResourceSupervisor()
        st = s.check()  # metrics default: ram_total=0 → ram_used=0
        self.assertEqual(st.level, "nominal")

    def test_can_start_worker_fake_metrics(self):
        s = ResourceSupervisor(get_metrics=lambda: NodeMetrics(
            rss_mb=100.0, cpu_pct=5.0, ram_total_mb=4000.0))
        self.assertTrue(s.can_start_worker())


if __name__ == "__main__":
    unittest.main()

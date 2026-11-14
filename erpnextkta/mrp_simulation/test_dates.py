# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import unittest
from datetime import date
from erpnextkta.mrp_simulation.dates import get_simulation_dates


class TestSimulationDates(unittest.TestCase):
	def test_dates_alignment(self):
		sched = get_simulation_dates(base_date=date(2026, 11, 16))  # Monday of W47
		self.assertEqual(sched.w_current_monday, date(2026, 11, 16))
		# MUSTERI-AVRUPA: delivery_date - 12 days = W_CURRENT_START
		self.assertEqual(sched.so_avrupa_delivery_date, date(2026, 11, 28))  # 16 + 12 = 28
		# MUSTERI-YERLI: delivery_date - 4 days = W_CURRENT_START
		self.assertEqual(sched.so_yerli_delivery_date, date(2026, 11, 20))  # 16 + 4 = 20
		# PO in W_NEXT (W+1)
		self.assertEqual(sched.w_next_monday, date(2026, 11, 23))
		self.assertEqual(sched.po_schedule_date, date(2026, 11, 25))
		# Yolda PR ETA in W+2
		self.assertEqual(sched.w_plus_2_monday, date(2026, 11, 30))
		self.assertEqual(sched.pr_yolda_eta, date(2026, 12, 2))
		# MR in W_NEXT (W+1)
		self.assertEqual(sched.mr_schedule_date, date(2026, 11, 27))

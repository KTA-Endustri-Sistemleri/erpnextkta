# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

"""KTA MRP Visual Simulation Module."""


def seed():
	from erpnextkta.mrp_simulation.seeder import seed as _seed

	return _seed()


def clean():
	from erpnextkta.mrp_simulation.cleaner import clean as _clean

	return _clean()

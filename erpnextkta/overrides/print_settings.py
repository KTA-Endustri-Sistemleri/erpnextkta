"""Custom barcode routing for print templates."""

from __future__ import annotations

import re
from typing import Iterable, List

import frappe
from frappe.utils import cint, cstr, flt

import erpnext.controllers.print_settings as core_print_settings
from erpnext.stock.serial_batch_bundle import (
	get_batches_from_bundle,
	get_serial_nos_from_bundle,
)


SERIAL_TEMPLATE = (
	"erpnextkta/templates/print_formats/includes/serial_no_barcodes.html"
)
BATCH_TEMPLATE = (
	"erpnextkta/templates/print_formats/includes/batch_no_barcodes.html"
)
SERIAL_AND_BATCH_TEMPLATE = (
	"erpnextkta/templates/print_formats/includes/serial_and_batch_no_barcodes.html"
)


def set_print_templates_for_item_table(doc, settings):
	"""Extend ERPNext template routing with barcode specific templates."""
	core_print_settings._original_set_print_templates_for_item_table(doc, settings)

	if not settings:
		return

	print_batch_barcodes = cint(getattr(settings, "print_batch_no_barcodes", 0))
	print_serial_barcodes = cint(getattr(settings, "print_serial_no_barcodes", 0))

	if not (print_batch_barcodes or print_serial_barcodes):
		return

	barcode_rows = _build_barcode_rows(
		doc.get("items"),
		include_serial=print_serial_barcodes,
		include_batch=print_batch_barcodes,
	)

	if not barcode_rows:
		return

	flags = getattr(doc, "flags", None) or frappe._dict()
	doc.flags = flags

	stock_settings = flags.get("stock_settings")
	if not stock_settings:
		stock_settings = frappe.get_cached_doc("Stock Settings")
		flags.stock_settings = stock_settings

	flags.serial_batch_barcode_rows = barcode_rows
	flags.serial_batch_barcode_options = _build_barcode_options(stock_settings)

	selected_template = _get_template_path(print_serial_barcodes, print_batch_barcodes)
	if not getattr(doc, "print_templates", None):
		doc.print_templates = {}

	doc.print_templates.update({"items": selected_template})


def _build_barcode_rows(items: Iterable, include_serial=False, include_batch=False) -> List[frappe._dict]:
	rows = []
	if not items:
		return rows

	for item in items:
		serial_numbers = []
		batch_numbers = []

		if include_serial:
			serial_numbers = _get_serial_numbers(item)
		if include_batch:
			batch_numbers = _get_batch_numbers(item)

		if not (serial_numbers or batch_numbers):
			continue

		rows.append(
			frappe._dict(
				{
					"item_code": item.item_code,
					"item_name": item.item_name or item.item_code,
					"description": item.get("description"),
					"qty": item.get("qty"),
					"uom": item.get("uom") or item.get("stock_uom"),
					"serial_numbers": serial_numbers,
					"batch_numbers": batch_numbers,
				}
			)
		)

	return rows


def _get_serial_numbers(item) -> List[str]:
	if item.get("serial_and_batch_bundle"):
		return get_serial_nos_from_bundle(item.serial_and_batch_bundle)

	return _split_values(item.get("serial_no"))


def _get_batch_numbers(item) -> List[frappe._dict]:
	results: List[frappe._dict] = []
	if item.get("serial_and_batch_bundle"):
		batch_map = get_batches_from_bundle(item.serial_and_batch_bundle)
		for batch_no, qty in batch_map.items():
			if not batch_no:
				continue
			results.append(
				frappe._dict({
					"batch_no": batch_no,
					"qty": abs(flt(qty)),
				})
			)
	elif item.get("batch_no"):
		results.append(
			frappe._dict(
				{
					"batch_no": item.batch_no,
					"qty": abs(flt(item.get("qty"))),
				}
			)
		)

	return results


def _split_values(value) -> List[str]:
	if not value:
		return []

	parts = [cstr(part).strip() for part in re.split(r"[\n,]", cstr(value)) if cstr(part).strip()]
	return parts


def _build_barcode_options(stock_settings):
	def pick(fieldnames, default=None):
		fieldnames = fieldnames if isinstance(fieldnames, (list, tuple)) else [fieldnames]
		for fieldname in fieldnames:
			val = stock_settings.get(fieldname)
			if val not in (None, ""):
				return val
		return default

	options = frappe._dict()
	options.barcode_format = pick(
		[
			"serial_barcode_format",
			"barcode_label_format",
			"serial_and_batch_barcode_format",
		],
		default="code128",
	)
	options.labels_per_row = cint(pick(["serial_barcode_labels_per_row", "barcode_labels_per_row"], 3)) or 3
	options.show_value = cint(pick(["serial_barcode_show_value", "barcode_show_value"], 1))
	options.show_item_info = cint(
		pick(["serial_barcode_show_item_info", "barcode_show_item_info"], 1)
	)
	options.font_family = pick(["serial_barcode_font", "barcode_font_family"], "monospace")
	font_size = pick(["serial_barcode_font_size", "barcode_font_size"], "10pt")
	options.font_size = font_size if isinstance(font_size, str) else f"{font_size}px"
	options.text_position = pick([
		"serial_barcode_value_position",
		"barcode_value_position",
	], "below")
	options.barcode_width = pick(["serial_barcode_width", "barcode_width"])
	options.barcode_height = pick(["serial_barcode_height", "barcode_height"])
	options.barcode_color = pick(["serial_barcode_color", "barcode_color"], "#000000")
	options.background_color = pick(
		["serial_barcode_background", "barcode_background_color"], "#ffffff"
	)
	options.quiet_zone = pick(["serial_barcode_quiet_zone", "barcode_quiet_zone"], 1)
	return options


def _get_template_path(print_serial_barcodes, print_batch_barcodes):
	if print_serial_barcodes and print_batch_barcodes:
		return SERIAL_AND_BATCH_TEMPLATE
	if print_serial_barcodes:
		return SERIAL_TEMPLATE
	return BATCH_TEMPLATE

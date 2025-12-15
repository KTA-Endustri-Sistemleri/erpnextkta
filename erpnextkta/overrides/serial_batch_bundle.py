import random
import string

import frappe


def before_insert(doc, _):
    if doc.name:
        return

    doc.name = _generate_bundle_name()


def _generate_bundle_name():
    chars = string.ascii_uppercase + string.digits
    for _ in range(10):
        candidate = "".join(random.choices(chars, k=8))
        if not frappe.db.exists("Serial and Batch Bundle", candidate):
            return candidate

    # Final fallback to frappe hash
    return frappe.generate_hash(length=8).upper()

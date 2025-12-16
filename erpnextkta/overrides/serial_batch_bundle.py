import random
import string

import frappe


BUNDLE_ID_LENGTH = 7


def before_insert(doc, _):
    if doc.name:
        return

    doc.name = _generate_bundle_name()


def _generate_bundle_name():
    chars = string.ascii_uppercase + string.digits
    for _ in range(20):
        candidate = "".join(random.choices(chars, k=BUNDLE_ID_LENGTH))
        if not frappe.db.exists("Serial and Batch Bundle", candidate):
            return candidate

    # Final fallback to frappe hash
    return frappe.generate_hash(length=BUNDLE_ID_LENGTH).upper()

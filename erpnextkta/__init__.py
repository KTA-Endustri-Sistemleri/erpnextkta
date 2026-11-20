__version__ = "4.5.1"

try:
    from erpnextkta.overrides import apply as apply_overrides

    apply_overrides()
except Exception:
    # Ignore during setup scenarios where dependencies may not be ready yet.
    pass

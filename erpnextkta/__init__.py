__version__ = "0.6.2"

try:
    from erpnextkta.overrides import apply as apply_overrides

    apply_overrides()
except Exception:
    # Ignore during setup scenarios where dependencies may not be ready yet.
    pass

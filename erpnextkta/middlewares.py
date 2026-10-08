import frappe

def update_website_context(context):
    """
    Route Guard Middleware for Website Docs
    Prevents unauthenticated access to /docs routes.
    """
    if getattr(frappe, "request", None) and frappe.request.path.startswith("/docs"):
        if frappe.session.user == "Guest":
            frappe.local.flags.redirect_location = f"/login?redirect-to={frappe.request.path}"
            raise frappe.Redirect

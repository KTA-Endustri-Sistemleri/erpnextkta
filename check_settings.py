import frappe

def check_settings():
    try:
        settings = frappe.get_doc("Selling Settings")
        print(f"maintain_same_sales_rate: {settings.maintain_same_sales_rate}")
        print(f"validate_selling_price: {settings.validate_selling_price}") # Checks if selling price is lower than purchase rate
        print(f"allow_user_to_edit_rate: {settings.allow_user_to_edit_rate}") # If this exists
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_settings()

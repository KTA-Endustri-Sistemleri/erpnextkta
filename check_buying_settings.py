import frappe

def check_buying_settings():
    try:
        settings = frappe.get_doc("Buying Settings")
        print(f"maintain_same_rate: {settings.maintain_same_rate}")
    except Exception as e:
        print(f"Error checking Buying Settings: {e}")

if __name__ == "__main__":
    check_buying_settings()

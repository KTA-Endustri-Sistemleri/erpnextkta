import frappe
from erpnextkta.kta_calisma_karti.api_impl.qc import (
    get_qc_templates_for_ck,
    get_template_details,
    submit_kta_quality_inspection
)

def test_qc_integration():
    """
    Manual verification script for QC integration.
    Run via: bench --site [site] execute erpnextkta.kta_calisma_karti.scripts.test_qc_integration.test_qc_integration
    """
    print("QC Integration Test Starting...")
    
    # 1. Find a Calisma Karti that is linked to a Job Card
    ck_name = frappe.db.get_value("Calisma Karti", {"docstatus": 0, "is_karti": ["!=", ""]}, "name")
    
    if not ck_name:
        print("Error: No active Calisma Karti with Job Card found for testing.")
        return

    print(f"Testing with Calisma Karti: {ck_name}")

    # 2. Test fetching templates
    templates_res = get_qc_templates_for_ck(ck_name)
    print(f"Available Templates: {len(templates_res['templates'])}")
    
    if not templates_res['templates']:
        print("Warning: No Quality Inspection Templates found in system.")
        return
        
    template_name = templates_res['templates'][0]['name']
    print(f"Selected Template for test: {template_name}")

    # 3. Test fetching details
    params = get_template_details(template_name)
    print(f"Parameters in template: {len(params)}")

    # 4. Mock readings
    readings = []
    for p in params:
        readings.append({
            "specification": p["specification"],
            "parameter": p["parameter"],
            "reading_1": 10 if p["numeric"] else "OK",
            "status": "Accepted",
            "numeric": p["numeric"],
            "min_value": p["min_value"],
            "max_value": p["max_value"]
        })

    # 5. Test submission
    print("Submitting Quality Inspection...")
    try:
        res = submit_kta_quality_inspection(ck_name, template_name, readings)
        print(f"Success! Created MAT-QA: {res['quality_inspection']}")
        
        # Verify CK state
        ck = frappe.get_doc("Calisma Karti", ck_name)
        print(f"CK Quality Control Status: {ck.kalite_kontrol}")
        print(f"CK Linked Inspection: {ck.quality_inspection}")
        
        if ck.kalite_kontrol == "Onaylandı" and ck.quality_inspection == res['quality_inspection']:
            print("Verification PASSED!")
        else:
            print("Verification FAILED: Linkage or status mismatch.")
            
    except Exception as e:
        print(f"Submission failed: {str(e)}")
        frappe.db.rollback()

if __name__ == "__main__":
    test_qc_integration()

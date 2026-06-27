import frappe

def execute():
    workflow_name = "KTA Mal Giris Sureci"
    if not frappe.db.exists("Workflow", workflow_name):
        return
        
    wf = frappe.get_doc("Workflow", workflow_name)
    
    # Remove unwanted states
    new_states = []
    for state in wf.states:
        if state.state not in ["Etiketleme", "GKK Bekliyor"]:
            new_states.append(state)
    wf.states = new_states
    
    # Remove unwanted transitions
    new_transitions = []
    for transition in wf.transitions:
        if transition.state not in ["Etiketleme", "GKK Bekliyor"] and transition.next_state not in ["Etiketleme", "GKK Bekliyor"]:
            new_transitions.append(transition)
    wf.transitions = new_transitions
    
    # Ensure Mal Giris goes to Kabul Edildi directly when approved
    has_mal_giris_approve = False
    for transition in wf.transitions:
        if transition.state == "Mal Giriş" and transition.action == "Approve":
            transition.next_state = "Kabul Edildi"
            has_mal_giris_approve = True
            
    if not has_mal_giris_approve:
        wf.append("transitions", {
            "state": "Mal Giriş",
            "action": "Approve",
            "next_state": "Kabul Edildi",
            "allowed": "Stock User"
        })
        
    wf.save()
    frappe.db.commit()

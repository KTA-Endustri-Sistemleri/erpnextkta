def get_modern_summary_html(summary_list):
    if not summary_list:
        return None
        
    cards_html = ""
    for item in summary_list:
        label = item.get("label", "").upper()
        value = item.get("value", 0)
        
        indicator = item.get("indicator", "Blue").lower()
        if indicator == "red":
            bg_color = "#fee2e2"
            text_color = "#ef4444"
            icon_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
        elif indicator == "green":
            bg_color = "#dcfce7"
            text_color = "#16a34a"
            icon_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>'
        elif indicator == "blue":
            bg_color = "#e0f2fe"
            text_color = "#0284c7"
            icon_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>'
        elif indicator == "orange" or indicator == "yellow":
            bg_color = "#ffedd5"
            text_color = "#ea580c"
            icon_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"></rect><circle cx="12" cy="12" r="2"></circle><path d="M6 12h.01M18 12h.01"></path></svg>'
        else:
            bg_color = "#f3e8ff"
            text_color = "#9333ea"
            icon_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
            
        if isinstance(value, (int, float)):
            formatted_val = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if formatted_val.endswith(",00"): formatted_val = formatted_val[:-3]
        else:
            formatted_val = str(value)
            
        cards_html += f"""
            <div class="mrp-summary-card">
                <div class="mrp-card-icon" style="background: {bg_color}; color: {text_color};">
                    {icon_svg}
                </div>
                <div class="mrp-card-content">
                    <div class="mrp-card-label">{label}</div>
                    <div class="mrp-card-value" style="color: {text_color};">{formatted_val}</div>
                </div>
            </div>
        """
        
    style = """
    <style>
        .mrp-summary-container {
            display: flex;
            flex-direction: column;
            gap: 16px;
            margin-bottom: 24px;
            padding: 4px 0;
        }
        .mrp-summary-row {
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            width: 100%;
        }
        .mrp-summary-card {
            flex: 1;
            min-width: 240px;
            background: linear-gradient(145deg, #ffffff, #f8fafc);
            border: 1px solid rgba(226, 232, 240, 0.8);
            border-radius: 12px;
            padding: 16px;
            display: flex;
            align-items: center;
            gap: 16px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03), 0 1px 2px rgba(0, 0, 0, 0.02);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .mrp-summary-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06), 0 2px 4px rgba(0, 0, 0, 0.04);
        }
        .mrp-card-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .mrp-card-content {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .mrp-card-label {
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            color: #64748b;
            text-transform: uppercase;
        }
        .mrp-card-value {
            font-size: 20px;
            font-weight: 800;
            line-height: 1.2;
            letter-spacing: -0.5px;
        }
    </style>
    """
    return f"{style}<div class='mrp-summary-container'><div class='mrp-summary-row'>{cards_html}</div></div>"

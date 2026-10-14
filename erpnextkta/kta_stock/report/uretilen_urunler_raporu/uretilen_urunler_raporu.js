frappe.query_reports["Uretilen Urunler Raporu"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "item_code",
            "label": __("Item"),
            "fieldtype": "Link",
            "options": "Item"
        }
    ],
    "after_datatable_render": function(datatable) {
        let report = frappe.query_report;
        
        // Hide standard grid and message area if needed
        report.$report.find('.datatable').hide();
        report.$report.find('.report-summary').hide();
        report.$report.find('.frappe-datatable').hide();
        
        let container = report.$report.find('#custom-table-container');
        if (!container.length) {
            report.$report.append('<div id="custom-table-container"></div>');
            container = report.$report.find('#custom-table-container');
        }
        
        // State for sorting and filtering
        report.custom_sort = report.custom_sort || { col: 'posting_date', order: 'desc' };
        report.custom_filters = report.custom_filters || {};
        
        // CSS
        let css = `
        <style>
            .modern-table-wrapper { background: white; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05); margin: 32px 8px 48px 8px; border: 1px solid #e5e7eb; overflow-x: auto; overflow-y: hidden; }
            .modern-table { display: flex; flex-direction: column; width: 100%; min-width: 1000px; font-family: 'Inter', sans-serif; }
            .modern-table thead, .modern-table tbody { display: flex; flex-direction: column; width: 100%; }
            .modern-table tr { display: flex; width: 100%; border-bottom: 1px solid #f3f4f6; transition: background-color 0.2s; }
            .modern-table thead tr { background-color: #f9fafb; border-bottom: 1px solid #e5e7eb; }
            .modern-table tbody tr:hover { background-color: #f9fafb; }
            .modern-table tbody tr:last-child { border-bottom: none; }
            
            .modern-table th, .modern-table td { 
                display: flex; 
                align-items: center; 
                padding: 10px 16px; /* Reduced from 16px 24px */
                color: #374151; 
                word-break: break-word;
                box-sizing: border-box;
            }
            .modern-table th { font-size: 12px; font-weight: 600; color: #6b7280; text-transform: uppercase; cursor: pointer; user-select: none; position: relative; }
            .modern-table td { font-size: 13px; }
            
            .modern-table th:hover { background-color: #f3f4f6; color: #374151; }
            .modern-table th.active-sort { color: #111827; font-weight: 700; }
            
            .modern-badge { padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; background-color: #dcfce7; color: #166534; }
            .modern-link { color: #2563eb; text-decoration: none; font-weight: 500; }
            .modern-link:hover { text-decoration: underline; color: #1d4ed8; }
            .modern-empty { padding: 30px; text-align: center; color: #6b7280; font-size: 14px; width: 100%; display: block; }
            .sort-icon { display: inline-block; margin-left: 5px; font-size: 10px; }
            
            .col-filter-row { background-color: #ffffff; border-bottom: 1px solid #e5e7eb; }
            .col-filter-row th { padding: 6px 16px; cursor: default; }
            .col-filter-row th:hover { background-color: transparent; }
            .col-filter-input { width: 100%; padding: 6px 10px; font-size: 12px; border: 1px solid #d1d5db; border-radius: 4px; box-sizing: border-box; text-transform: none; color: #374151; font-weight: 400; font-family: 'Inter', sans-serif;}
            .col-filter-input:focus { outline: none; border-color: #2563eb; box-shadow: 0 0 0 1px #2563eb; }
            
            .numeric-filter-wrapper { display: flex; width: 100%; border: 1px solid #d1d5db; border-radius: 4px; overflow: hidden; background: white; }
            .numeric-filter-wrapper:focus-within { border-color: #2563eb; box-shadow: 0 0 0 1px #2563eb; }
            .numeric-operator-btn { background: #f3f4f6; border: none; border-right: 1px solid #d1d5db; padding: 0 8px; font-size: 12px; font-weight: 600; color: #4b5563; cursor: pointer; min-width: 32px; display: flex; align-items: center; justify-content: center; user-select: none; transition: background 0.2s; }
            .numeric-operator-btn:hover { background: #e5e7eb; color: #111827; }
            .numeric-filter-wrapper .col-filter-input { border: none !important; border-radius: 0 !important; box-shadow: none !important; }
            
            @media (max-width: 768px) {
                .modern-table thead { display: none; }
                .modern-table tr { flex-direction: column; padding: 8px 0; margin-bottom: 8px; border-bottom: 1px solid #e5e7eb; }
                .modern-table td { width: 100%; justify-content: space-between; padding: 8px 16px; border-bottom: 1px solid #f3f4f6; }
                .modern-table td::before { content: attr(data-label); font-size: 12px; font-weight: 600; color: #6b7280; text-transform: uppercase; }
            }
            
            #report-chart-container .chart-legend { display: none !important; }
        </style>`;

        // Dynamic columns logic
        let columns = report.columns || [];
        
        let thead_html = '<tr>';
        let filter_html = '<tr class="col-filter-row">';
        
        columns.forEach(col => {
            let label = col.label || col.fieldname;
            let flex_style = col.width ? `style="flex: 1 1 ${col.width}px;"` : `style="flex: 1 1 120px;"`;
            
            thead_html += `<th data-sort="${col.fieldname}" ${flex_style}>${label} <span class="sort-icon"></span></th>`;
            
            let is_numeric = ['Float', 'Int', 'Currency'].includes(col.fieldtype);
            let current_filter = (report.custom_filters[col.fieldname] || '').toString();
            
            if (is_numeric) {
                let op = '=';
                let val = current_filter;
                if (current_filter.startsWith('>=')) { op = '>='; val = current_filter.substring(2).trim(); }
                else if (current_filter.startsWith('<=')) { op = '<='; val = current_filter.substring(2).trim(); }
                else if (current_filter.startsWith('!=')) { op = '!='; val = current_filter.substring(2).trim(); }
                else if (current_filter.startsWith('>')) { op = '>'; val = current_filter.substring(1).trim(); }
                else if (current_filter.startsWith('<')) { op = '<'; val = current_filter.substring(1).trim(); }
                else if (current_filter.startsWith('=')) { op = '='; val = current_filter.substring(1).trim(); }
                
                filter_html += `<th ${flex_style}>
                    <div class="numeric-filter-wrapper">
                        <button class="numeric-operator-btn" type="button" title="${__('Toggle Operator')}">${op}</button>
                        <input type="text" class="col-filter-input" data-col="${col.fieldname}" placeholder="${__('Search')}..." value="${val}">
                    </div>
                </th>`;
            } else {
                filter_html += `<th ${flex_style}><input type="text" class="col-filter-input" data-col="${col.fieldname}" placeholder="${__('Search')}..." value="${current_filter}"></th>`;
            }
        });
        
        thead_html += '</tr>' + filter_html + '</tr>';

        // HTML wrapper
        let html = css + `
        <div id="report-chart-container" style="margin-top: 20px;"></div>
        <div class="modern-table-wrapper">
            <table class="modern-table">
                <thead>
                    ${thead_html}
                </thead>
                <tbody id="modern-table-body">
                </tbody>
            </table>
        </div>`;
        
        container.html(html);

        let data = report.data || [];
        
        function render_tbody() {
            let tbody = container.find('#modern-table-body');
            let rows_html = '';
            
            // Update headers
            container.find('th[data-sort]').removeClass('active-sort');
            container.find('th[data-sort] .sort-icon').html('');
            let active_th = container.find(`th[data-sort="${report.custom_sort.col}"]`);
            if (active_th.length) {
                active_th.addClass('active-sort');
                active_th.find('.sort-icon').html(report.custom_sort.order === 'asc' ? '▲' : '▼');
            }
            
            // Apply Filters
            let filtered_data = data.filter(row => {
                // Ensure we don't display Frappe's total row if it somehow got through
                if (row.stock_entry === 'Total' || row.item_code === 'Total') return false;
                
                for (let col_name in report.custom_filters) {
                    let search_term = report.custom_filters[col_name].toString().toLowerCase().trim();
                    if (!search_term) continue;
                    
                    let col_def = columns.find(c => c.fieldname === col_name);
                    let is_numeric = col_def && ['Float', 'Int', 'Currency'].includes(col_def.fieldtype);
                    
                    // Advanced Numeric Filtering
                    if (is_numeric) {
                        let num_val = parseFloat(row[col_name]) || 0;
                        let operator = '';
                        let target_num_str = '';
                        
                        if (search_term.startsWith('>=')) { operator = '>='; target_num_str = search_term.substring(2); }
                        else if (search_term.startsWith('<=')) { operator = '<='; target_num_str = search_term.substring(2); }
                        else if (search_term.startsWith('!=')) { operator = '!='; target_num_str = search_term.substring(2); }
                        else if (search_term.startsWith('>')) { operator = '>'; target_num_str = search_term.substring(1); }
                        else if (search_term.startsWith('<')) { operator = '<'; target_num_str = search_term.substring(1); }
                        else if (search_term.startsWith('=')) { operator = '='; target_num_str = search_term.substring(1); }
                        
                        if (operator) {
                            let target_num = parseFloat(target_num_str.trim());
                            if (!isNaN(target_num)) {
                                if (operator === '>' && !(num_val > target_num)) return false;
                                if (operator === '<' && !(num_val < target_num)) return false;
                                if (operator === '>=' && !(num_val >= target_num)) return false;
                                if (operator === '<=' && !(num_val <= target_num)) return false;
                                if (operator === '=' && !(num_val === target_num)) return false;
                                if (operator === '!=' && !(num_val !== target_num)) return false;
                                continue; // Passed numeric filter!
                            }
                        }
                    }
                    
                    // Standard Text Fallback
                    let cell_value = row[col_name];
                    if (cell_value === null || cell_value === undefined) cell_value = '';
                    
                    if (col_def) {
                        cell_value = frappe.format(cell_value, col_def, { no_icon: true });
                        cell_value = $(`<span>${cell_value}</span>`).text().toLowerCase();
                    } else {
                        cell_value = cell_value.toString().toLowerCase();
                    }
                    
                    if (cell_value.indexOf(search_term) === -1) {
                        return false;
                    }
                }
                return true;
            });

            if (filtered_data.length > 0) {
                filtered_data.forEach(row => {
                    rows_html += '<tr>';
                    
                    columns.forEach(col => {
                        let val = row[col.fieldname];
                        if (col.fieldname === 'customer_group' && val === 'Undefined') {
                            val = __('Undefined');
                        }
                        
                        let formatted_val = frappe.format(val, col, { no_icon: true });
                        let flex_style = col.width ? `style="flex: 1 1 ${col.width}px;"` : `style="flex: 1 1 120px;"`;
                        
                        if (col.fieldname === 'qty') {
                            formatted_val = `<span class="modern-badge">${val || 0}</span>`;
                        } else if (col.fieldtype === 'Link' && val && typeof val === 'string') {
                            formatted_val = `<a href="/app/${col.options.toLowerCase().replace(/ /g, '-')}/${val}" class="modern-link">${val}</a>`;
                        }
                        
                        rows_html += `<td data-label="${col.label || col.fieldname}" ${flex_style}>${formatted_val}</td>`;
                    });
                    
                    rows_html += '</tr>';
                });
            } else {
                rows_html = `<tr><td colspan="${columns.length}"><div class="modern-empty">${__('No data found')}</div></td></tr>`;
            }
            tbody.html(rows_html);
            render_chart(filtered_data);
        }

        function render_chart(chart_data) {
            let container_div = container.find('#report-chart-container')[0];
            if (!container_div) return;

            let group_totals = {};
            chart_data.forEach(row => {
                // Ignore the summary row if it somehow bypassed filters
                if (row.stock_entry === 'Total') return;
                
                let cg = __(row.customer_group || 'Undefined');
                let qty = parseFloat(row.qty) || 0;
                group_totals[cg] = (group_totals[cg] || 0) + qty;
            });

            // Function to abbreviate large numbers (e.g. 114253 -> 114.3K)
            function short_format(num) {
                if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
                if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
                return num.toString();
            }

            let raw_labels = Object.keys(group_totals);
            let values = Object.values(group_totals).map(v => Number(v.toFixed(2)));

            if (values.length === 0 || values.every(v => v === 0)) {
                container_div.innerHTML = '';
                return;
            }

            let colors = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#f97316', '#14b8a6'];

            // Using Frappe Chart without native legend
            new frappe.Chart(container_div, {
                title: __('Müşteri Grubuna Göre Üretim (Miktar)'),
                data: {
                    labels: raw_labels,
                    datasets: [
                        { values: values }
                    ]
                },
                type: 'donut',
                height: 340,
                colors: colors,
                tooltipOptions: {
                    formatTooltipX: d => (d + '').toUpperCase(),
                    formatTooltipY: d => format_number(d)
                }
            });
            
            // Modernize the chart container styling
            $(container_div).css({
                'background': 'white',
                'border-radius': '12px',
                'box-shadow': '0 4px 6px -1px rgba(0,0,0,0.05)',
                'border': '1px solid #e5e7eb',
                'padding': '16px',
                'margin': '16px 8px'
            });

            // Build custom HTML legend for perfect wrapping
            let custom_legend = '<div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 16px; margin-top: -30px; padding-bottom: 10px;">';
            raw_labels.forEach((label, i) => {
                let color = colors[i % colors.length];
                let valStr = short_format(Math.round(group_totals[label]));
                custom_legend += `
                <div style="display: flex; align-items: center; font-size: 13px; color: #4b5563; font-weight: 500;">
                    <span style="display: inline-block; width: 12px; height: 12px; border-radius: 3px; background-color: ${color}; margin-right: 6px;"></span>
                    ${label} (${valStr})
                </div>`;
            });
            custom_legend += '</div>';
            
            $(container_div).append(custom_legend);
        }

        // Client-side Sort Logic
        function sort_data(col, order) {
            let col_def = columns.find(c => c.fieldname === col);
            let is_numeric = col_def && ['Float', 'Int', 'Currency'].includes(col_def.fieldtype);
            let is_date = col_def && ['Date', 'Datetime'].includes(col_def.fieldtype);
            
            data.sort((a, b) => {
                let valA = a[col];
                let valB = b[col];
                
                // Handle null/undefined
                if (valA === null || valA === undefined) valA = '';
                if (valB === null || valB === undefined) valB = '';
                
                if (is_numeric || col === 'qty') {
                    valA = parseFloat(valA) || 0;
                    valB = parseFloat(valB) || 0;
                } else if (is_date || col === 'posting_date') {
                    valA = valA ? new Date(valA).getTime() : 0;
                    valB = valB ? new Date(valB).getTime() : 0;
                } else {
                    valA = valA.toString().toLowerCase();
                    valB = valB.toString().toLowerCase();
                }

                if (valA < valB) return order === 'asc' ? -1 : 1;
                if (valA > valB) return order === 'asc' ? 1 : -1;
                return 0;
            });
        }
        
        // Event Listeners for sorting
        container.find('th[data-sort]').on('click', function() {
            let col = $(this).attr('data-sort');
            if (report.custom_sort.col === col) {
                report.custom_sort.order = report.custom_sort.order === 'asc' ? 'desc' : 'asc';
            } else {
                report.custom_sort.col = col;
                report.custom_sort.order = 'asc';
            }
            sort_data(report.custom_sort.col, report.custom_sort.order);
            render_tbody();
        });
        
        // Event Listeners for column filtering
        container.find('.numeric-operator-btn').on('click', function(e) {
            e.stopPropagation(); // prevent sorting if clicked
            let ops = ['=', '>', '<', '>=', '<=', '!='];
            let current = $(this).text().trim();
            let next_idx = (ops.indexOf(current) + 1) % ops.length;
            let next_op = ops[next_idx];
            $(this).text(next_op);
            
            // Trigger input update
            $(this).siblings('.col-filter-input').trigger('input');
        });

        container.find('.col-filter-input').on('input', function() {
            let col = $(this).attr('data-col');
            let val = $(this).val();
            
            let btn = $(this).siblings('.numeric-operator-btn');
            if (btn.length && val.trim() !== '') {
                val = btn.text().trim() + ' ' + val;
            }
            
            report.custom_filters[col] = val;
            render_tbody();
        });

        // Initialize table
        sort_data(report.custom_sort.col, report.custom_sort.order);
        render_tbody();
    }
};

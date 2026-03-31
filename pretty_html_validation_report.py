import numpy as np
import pandas as pd
import pandera.pandas as pa
from pathlib import Path
from datetime import datetime

def generate_dq_report(
    exception, 
    output_path: str, 
    max_samples_per_check: int = 10
) -> None:
    
    if not hasattr(exception, 'failure_cases'):
        raise ValueError("Input exception must be a pandera.SchemaErrors object")

    # 1. Get the failure dataframe
    df_errs = exception.failure_cases.copy()
    
    if df_errs is None or len(df_errs) == 0:
        html_content = "<h1>No Validation Errors Found</h1>"
        Path(output_path).write_text(html_content, encoding='utf-8')
        return

    df_errs['column'] = np.where(df_errs['schema_context'] == 'DataFrameSchema', 'TABLE-LEVEL', df_errs['column'])
    df_errs['failure_case'] = np.where(df_errs['schema_context'] == 'DataFrameSchema', 'N/A', df_errs['failure_case'])
    
    df_errs['column'] = df_errs['column'].fillna('TABLE-LEVEL')

    # 2. Deduplicate based on 'column', 'check', and 'index'
    # This prevents the "one per column" duplication for table-level checks
    df_errs = df_errs.drop_duplicates(subset=['column', 'check', 'index'])

    # --- Summary Data ---
    summary_df = df_errs.groupby(['column', 'check']).size().reset_index(name='Total_Failures')
    summary_df = summary_df.sort_values(by='Total_Failures', ascending=False).reset_index(drop=True)
    summary_df.columns = ['Scope/Column', 'Check Description', 'Count']

    # --- Detailed Tables ---
    detail_tables_html = []
    
    for (col_name, check_logic), group in df_errs.groupby(['column', 'check']):
        total_count = len(group)
        sample_group = group.head(max_samples_per_check).copy()
        
        display_text = f"Showing {len(sample_group)} of {total_count} failures" if total_count > max_samples_per_check else "All failures shown"
        
        # If it's a table-level check, the 'failure_case' is often a giant string of the whole row.
        # We clean it up or wrap it for the UI.
        def clean_failure_value(v):
            v_str = str(v)
            if len(v_str) > 150:
                return f'<div class="long-content">{v_str}</div>'
            return f"<code>{v_str}</code>"

        sample_group['failure_case'] = sample_group['failure_case'].apply(clean_failure_value)
        
        # We only need the Index and the Failure Case (the value that caused the error)
        display_cols = ['index', 'failure_case']
        html_table = sample_group[display_cols].to_html(
            index=False,
            escape=False,
            classes='table table-hover mb-0 detail-table',
            border=0
        ) 
        
        # Use different colors for Column errors vs Table-level errors
        header_color = "table-danger" if col_name == "TABLE-LEVEL" else "bg-light"
        badge_color = "bg-danger" if col_name == "TABLE-LEVEL" else "bg-secondary"

        detail_tables_html.append(f"""
            <div class="card mb-4 shadow-sm border-0">
                <div class="card-header {header_color} d-flex justify-content-between align-items-center py-3">
                    <h6 class="mb-0">
                        <span class="badge {badge_color} me-2">{col_name}</span> 
                        <span class="text-dark">{check_logic}</span>
                    </h6>
                    <small class="text-muted">{display_text}</small>
                </div>
                <div class="card-body p-0">
                    {html_table}
                </div>
            </div>
        """)

    # --- HTML Template ---
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>DQ Report</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #f4f7f6; padding: 40px 20px; font-family: 'Inter', sans-serif; }}
            .container {{ max-width: 1000px; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }}
            
            /* Table Styling */
            .table th {{ background-color: #f8f9fa !important; font-size: 0.75rem; text-transform: uppercase; color: #6c757d; padding: 12px 20px !important; border-bottom: 2px solid #dee2e6 !important; }}
            .table td {{ padding: 12px 20px !important; vertical-align: middle; border-bottom: 1px solid #eee; font-size: 0.9rem; }}
            
            .summary-table-wrapper {{ display: inline-block; min-width: 100%; border: 1px solid #eee; border-radius: 8px; overflow: hidden; margin-bottom: 40px; }}
            .summary-table {{ margin-bottom: 0; width: 100% !important; }}

            .detail-table {{ table-layout: fixed; width: 100%; }}
            .detail-table td:first-child {{ width: 120px; font-family: monospace; font-weight: bold; color: #0d6efd; }}
            
            /* Handling the massive strings from multi-column checks */
            .long-content {{
                max-height: 80px;
                overflow-y: auto;
                font-size: 0.75rem;
                color: #d63384;
                background: #fff0f7;
                padding: 8px;
                border-radius: 4px;
                word-break: break-all;
                white-space: pre-wrap;
            }}
            code {{ color: #d63384; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2 class="mb-4 text-dark font-weight-bold">Validation Report</h2>
            
            <div class="p-3 mb-5 bg-light rounded-3 border d-flex justify-content-between align-items-center">
                <div>
                    <div class="text-muted small uppercase">Timestamp</div>
                    <strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</strong>
                </div>
                <div class="text-end">
                    <div class="text-muted small uppercase">Total Violations</div>
                    <strong class="text-danger fs-4">{len(df_errs)}</strong>
                </div>
            </div>

            <h5 class="mb-3 text-secondary">📊 Summary</h5>
            <div class="summary-table-wrapper">
                {summary_df.to_html(classes='table summary-table', index=False)}
            </div>

            <h5 class="mb-3 text-secondary">🔍 Details</h5>
            {''.join(detail_tables_html)}
        </div>
    </body>
    </html>
    """

    Path(output_path).write_text(html_template, encoding='utf-8')
    print(f"Validation report saved to: {output_path}")
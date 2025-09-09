from bs4 import BeautifulSoup
from .parse import parse_payroll
from .excel_writer import write_excel
from .pdf_writer import write_pdf
from .utils import ensure_dir, join
from flask import abort, session

def process_payroll(
    html_path: str,
    pdf_root: str = "./pdf",
    excel_root: str = "./excel",
    template_path: str = "./form/Original Form (Do Not Delete).pdf",
    claim_number: str | None = None,
    date_loss: str | None = None,
):
    # --- read file once (keep both html text and soup) ---
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        abort(400, description=f"Couldn’t read the HTML file: {e}")

    soup = BeautifulSoup(html, "lxml")

    # --- Toast/payroll signature checks ---
    has_header_table = bool(soup.select_one("#ReportHeaderTable"))
    has_check_dates = any(
        "check dates:" in td.get_text(strip=True).lower()
        for td in soup.select("td.ReportHeaderLabel")
    )
    has_pay_rows = bool(soup.select("tr.BottomBorder"))

    if not has_header_table or not has_check_dates:
        abort(400, description="Invalid file: Not the right Toast payroll export. Please check and try again.")

    if not has_pay_rows:
        abort(400, description="Invalid file: Toast report detected, but no payroll rows found.")

    # --- parse structured data ---
    parsed = parse_payroll(html)
    employee_name  = parsed["employee_name"]
    date_range     = parsed["date_range"]
    rows           = parsed["rows"]

    claim_number = (claim_number or session.get("claim_number") or "").strip()
    date_loss    = (date_loss    or session.get("date_loss")    or "").strip()

    # --- ensure output dirs (per-employee) ---
    pdf_out_dir   = join(pdf_root, employee_name)
    excel_out_dir = join(excel_root, employee_name)
    ensure_dir(pdf_out_dir)
    ensure_dir(excel_out_dir)

    # --- write artifacts ---
    pdf_path   = write_pdf(template_path, pdf_out_dir, employee_name, claim_number, date_loss, date_range, rows)
    excel_path = write_excel(excel_out_dir, employee_name, date_range, rows)

    return pdf_path, excel_path

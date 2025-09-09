from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from .utils import ensure_dir, join

def write_pdf(template_path: str, output_dir: str, employee_name: str, claim_number: str, date_loss: str, date_range: str, rows: list) -> str:
    ensure_dir(output_dir)
    file_name_date = date_range.replace("/", ".")
    path = join(output_dir, f"Wage Information Request_{file_name_date}.pdf")

    reader = PdfReader(template_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    if "/AcroForm" in reader.trailer["/Root"]:
        writer._root_object.update({
            NameObject("/AcroForm"): reader.trailer["/Root"]["/AcroForm"]
        })

    # Build field map
    form_data = {}
    for i, entry in enumerate(rows, start=1):
        form_data[f"FROM{i}"] = entry["From"]
        form_data[f"TO{i}"] = entry["To"]
        form_data[f"GROSS{i}"] = entry["Gross"]
    form_data["Name_Text"] = employee_name
    form_data["Claim_Text"] = claim_number
    form_data["Date_Text"] = date_loss

    writer.update_page_form_field_values(writer.pages[0], form_data)
    with open(path, "wb") as f:
        writer.write(f)

    return path

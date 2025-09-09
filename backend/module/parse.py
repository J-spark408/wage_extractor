import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

def parse_payroll(html_text: str):
    soup = BeautifulSoup(html_text, "lxml")

    # Employee name
    rows = soup.find_all("tr", class_="BottomBorder")
    name_cell = rows[0].find_all("td")[1]
    raw_name_text = name_cell.get_text(strip=True)
    m = re.search(r"([A-Za-z\s]+,\s*[A-Za-z\s]+)", raw_name_text)
    employee_name = m.group(1).strip() if m else "Unknown Employee"

    # Date range (header)
    date_range = "Unknown"
    for tr in soup.select("table#ReportHeaderTable tr"):
        label_td = tr.find("td", class_="ReportHeaderLabel")
        if label_td and "Check Dates:" in label_td.get_text():
            value_td = tr.find("td", class_="ReportHeaderField")
            if value_td:
                date_range = value_td.get_text(strip=True)
            break

    # Rows
    data = []
    for row in rows:
        biweekly_cell = row.find("td", class_="ReportDetailLarge")
        if not biweekly_cell:
            continue

        biweekly_text = biweekly_cell.get_text(strip=True)
        if "Biweekly" in biweekly_text:
            biweekly_date_str = biweekly_text.split("-")[-1].strip()
        else:
            biweekly_date_str = "Unknown"

        mmddyyyy = re.findall(r"\d{1,2}/\d{1,2}/\d{4}", biweekly_date_str)
        biweekly_date_str = mmddyyyy[0] if mmddyyyy else "Unknown"

        try:
            biweekly_date = datetime.strptime(biweekly_date_str, "%m/%d/%Y")
            pay_begin_date = (biweekly_date - timedelta(days=19)).strftime("%m/%d/%Y")
            pay_end_date   = (biweekly_date - timedelta(days=6)).strftime("%m/%d/%Y")
        except Exception:
            pay_begin_date = "Unknown"
            pay_end_date   = "Unknown"

        gross_pay = "Not Found"
        next_table = row.find_next("table", class_="tinyReportTable")
        if next_table:
            total_row = next((tr for tr in next_table.find_all("tr") if "Total:" in tr.get_text()), None)
            if total_row:
                tds = total_row.find_all("td")
                if len(tds) >= 4:
                    gross_pay = tds[-1].get_text(strip=True)

        data.append({"From": pay_begin_date, "To": pay_end_date, "Gross": gross_pay})

    # Add week numbers
    for i, entry in enumerate(data, start=1):
        entry["Week"] = f"{i}"

    return {
        "employee_name": employee_name,
        "date_range": date_range,
        "rows": data,
    }


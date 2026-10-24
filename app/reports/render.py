from app.reports.pdf import to_pdf
from app.reports.text_formats import to_csv, to_json, to_xml

RENDER = {"json": to_json, "csv": to_csv, "xml": to_xml, "pdf": to_pdf}
MEDIA = {"json": "application/json", "csv": "text/csv; charset=utf-8", "xml": "application/xml",
         "pdf": "application/pdf"}

from io import BytesIO
from reportlab.pdfgen import canvas

def generate_receipt_pdf(receipt_no: str, customer_name: str, amount: float, currency: str) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 800, "SmartServe Payment Receipt")

    c.setFont("Helvetica", 12)
    c.drawString(50, 760, f"Receipt No: {receipt_no}")
    c.drawString(50, 740, f"Customer: {customer_name}")
    c.drawString(50, 720, f"Amount: {amount:.2f} {currency}")

    c.showPage()
    c.save()

    return buffer.getvalue()

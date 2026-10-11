from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)


def generate_invoice_pdf(
    invoice_number,
    invoice_date,
    customer_name,
    customer_phone,
    customer_email,
    customer_address,
    car_brand,
    car_model,
    quantity,
    unit_price,
):
    """Generate a PDF invoice for an existing sale without changing the database."""

    quantity = int(quantity)
    unit_price = float(unit_price)

    if quantity <= 0 or unit_price < 0:
        raise ValueError("Quantity must be positive and price cannot be negative.")

    total = quantity * unit_price
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice {invoice_number}",
        author="CollectWithAkash",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="StoreTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=27,
        textColor=colors.HexColor("#17365D"),
        alignment=0,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#17365D"),
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name="SmallInvoice",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
    ))

    story = []

    header = Table(
        [
            [
                Paragraph("CollectWithAkash", styles["StoreTitle"]),
                Paragraph("INVOICE", styles["InvoiceTitle"]),
            ],
            [
                Paragraph("Diecast Store Manager", styles["SmallInvoice"]),
                Paragraph(
                    f"<b>Invoice No:</b> {escape(str(invoice_number))}<br/>"
                    f"<b>Date:</b> {escape(str(invoice_date))}",
                    styles["SmallInvoice"],
                ),
            ],
        ],
        colWidths=[90 * mm, 80 * mm],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    story.extend([
        header,
        Spacer(1, 6 * mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#17365D")),
        Spacer(1, 6 * mm),
        Paragraph("BILL TO", styles["Heading2"]),
    ])

    customer_lines = [
        f"<b>{escape(str(customer_name or 'Walk-in Customer'))}</b>"
    ]
    if customer_phone:
        customer_lines.append(f"Phone: {escape(str(customer_phone))}")
    if customer_email:
        customer_lines.append(f"Email: {escape(str(customer_email))}")
    if customer_address:
        customer_lines.append(f"Address: {escape(str(customer_address))}")

    story.extend([
        Paragraph("<br/>".join(customer_lines), styles["SmallInvoice"]),
        Spacer(1, 10 * mm),
    ])

    items = [
        ["Description", "Qty", "Unit Price (INR)", "Amount (INR)"],
        [
            Paragraph(
                escape(f"{car_brand} {car_model}"),
                styles["SmallInvoice"],
            ),
            str(quantity),
            f"{unit_price:,.2f}",
            f"{total:,.2f}",
        ],
    ]

    item_table = Table(
        items,
        colWidths=[75 * mm, 20 * mm, 35 * mm, 40 * mm],
        repeatRows=1,
    )
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E2F3")),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))

    story.extend([item_table, Spacer(1, 8 * mm)])

    totals = Table(
        [
            ["Subtotal", f"INR {total:,.2f}"],
            ["Grand Total", f"INR {total:,.2f}"],
        ],
        colWidths=[130 * mm, 40 * mm],
    )
    totals.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#EAF0F8")),
        ("LINEABOVE", (0, 1), (-1, 1), 1, colors.HexColor("#17365D")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    story.extend([
        totals,
        Spacer(1, 18 * mm),
        Paragraph(
            "Thank you for your purchase!",
            ParagraphStyle(
                name="Thanks",
                parent=styles["Normal"],
                alignment=TA_CENTER,
                fontSize=12,
                textColor=colors.HexColor("#17365D"),
            ),
        ),
        Spacer(1, 3 * mm),
        Paragraph(
            "CollectWithAkash | Diecast Store Manager",
            ParagraphStyle(
                name="InvoiceFooter",
                parent=styles["SmallInvoice"],
                alignment=TA_CENTER,
            ),
        ),
    ])

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

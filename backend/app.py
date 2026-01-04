# =====================================================
# IMPORTS
# =====================================================
from flask import Flask, render_template, request, session, jsonify, send_from_directory
from datetime import date
import time, os, uuid
from backend.db import get_connection

# ReportLab – Enhanced Professional Invoice
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
from reportlab.lib.pagesizes import A4
from reportlab.lib. styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.lib. units import mm
from reportlab.pdfgen import canvas

# =====================================================
# PATH SETUP
# =====================================================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GENERATED_BILLS_DIR = os.path.join(BASE_DIR, "generated_bills")
os.makedirs(GENERATED_BILLS_DIR, exist_ok=True)

# =====================================================
# APP SETUP
# =====================================================
app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
    static_url_path="/static"
)
app.secret_key = "slaydrip_secret_key"

# =====================================================
# CUSTOM PAGE TEMPLATE WITH WATERMARK
# =====================================================
class InvoiceCanvas(canvas.Canvas):
    """Custom canvas to add watermark and footer"""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self.pages)
        for page_num, page in enumerate(self.pages, 1):
            self.__dict__. update(page)
            self.draw_watermark()
            self.draw_footer(page_num, page_count)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_watermark(self):
        """Add subtle watermark"""
        self.saveState()
        self.setFont("Helvetica-Bold", 60)
        self.setFillColor(colors.Color(0.9, 0.9, 0.9, alpha=0.3))
        self.translate(A4[0]/2, A4[1]/2)
        self.rotate(45)
        self.drawCentredString(0, 0, "SLAYDRIP")
        self.restoreState()

    def draw_footer(self, page_num, page_count):
        """Add professional footer"""
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.grey)
        
        # Footer line
        self.setStrokeColor(colors.Color(0.8, 0.8, 0.8))
        self.setLineWidth(0.5)
        self.line(20*mm, 15*mm, A4[0]-20*mm, 15*mm)
        
        # Footer text
        footer_text = "SLAYDRIP | Premium Fashion Wear | Contact: info@slaydrip.com | www.slaydrip.com"
        self.drawCentredString(A4[0]/2, 11*mm, footer_text)
        
        # Page number
        self.drawRightString(A4[0]-20*mm, 11*mm, f"Page {page_num} of {page_count}")
        
        self.restoreState()

# =====================================================
# HOME
# =====================================================
@app. route("/")
def home():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT design_id, design_code, product_name, gender, color, price
        FROM designs
    """)
    designs = cursor. fetchall()

    cursor.execute("SELECT discount_percent FROM store_settings WHERE id=1")
    discount_percent = cursor.fetchone()["discount_percent"]

    cursor.close()
    conn.close()

    return render_template("index.html", designs=designs, discount_percent=discount_percent)

# =====================================================
# GET SIZES
# =====================================================
@app.route("/get-sizes/<int:design_id>")
def get_sizes(design_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT size FROM design_stock
        WHERE design_id=%s AND stock>0
    """, (design_id,))

    sizes = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(sizes)

# =====================================================
# SAVE CART
# =====================================================
@app.route("/save-cart", methods=["POST"])
def save_cart():
    session["cart"] = request.json. get("cart", [])
    session.modified = True
    return jsonify({"status": "saved"})

# =====================================================
# CHECKOUT
# =====================================================
@app.route("/checkout", methods=["POST"])
def checkout():
    cart = session.get("cart", [])
    if not cart:
        return "Cart empty", 400

    # -------- FORM DATA --------
    customer_name = request.form["customer_name"]
    phone = request.form["phone"]
    payment_mode = request.form["payment_mode"]
    discount_percent = float(request.form. get("discount_percent") or 0)

    # -------- DB --------
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT gst_percent FROM store_settings WHERE id=1")
    default_gst_percent = float(cursor.fetchone()["gst_percent"])

    cursor.execute("SELECT last_number FROM invoice_counter WHERE id=1")
    last_no = cursor.fetchone()["last_number"] + 1
    cursor.execute("UPDATE invoice_counter SET last_number=%s WHERE id=1", (last_no,))

    invoice_no = f"INV-{last_no:05d}"
    bill_no = f"BILL-{int(time.time())}"
    bill_date = date.today()

    # =====================================================
    # 💰 NEW CALCULATION LOGIC (GST INCLUSIVE)
    # =====================================================
    
    # Step 1: Calculate subtotal from GST-inclusive prices
    subtotal_inclusive = sum(i["price"] * i["quantity"] for i in cart)
    
    # Step 2: Extract base price (remove GST from entered price) - using default GST for initial calculation
    gst_multiplier = 1 + (default_gst_percent / 100)
    base_price_total = subtotal_inclusive / gst_multiplier
    
    # Step 3: Calculate GST amount that was included in the price
    gst_in_original = subtotal_inclusive - base_price_total
    
    # Step 4: Apply discount on base price
    discount_amount = base_price_total * discount_percent / 100
    discounted_base_price = base_price_total - discount_amount
    
    # Step 5: Determine GST percentage based on discounted base price
    if discounted_base_price < 1500:
        gst_percent = 5
    else:
        gst_percent = 12
    
    # Step 6: Calculate GST on discounted base price
    gst_amount = discounted_base_price * gst_percent / 100
    
    # Step 7: Final Grand Total (discounted base + GST)
    grand_total = discounted_base_price + gst_amount

    # =====================================================
    # 🎨 PROFESSIONAL PDF GENERATION
    # =====================================================
    pdf_filename = f"SLAYDRIP_{uuid.uuid4().hex[:6]}.pdf"
    pdf_path = os.path.join(GENERATED_BILLS_DIR, pdf_filename)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=25*mm
    )

    # =====================================================
    # 🎨 CUSTOM STYLES
    # =====================================================
    styles = getSampleStyleSheet()
    
    # Brand Header Style
    styles.add(ParagraphStyle(
        name="BrandHeader",
        fontSize=28,
        fontName="Helvetica-Bold",
        textColor=colors.Color(0.1, 0.1, 0.1),
        spaceAfter=2,
        leading=32
    ))
    
    # Tagline Style
    styles. add(ParagraphStyle(
        name="Tagline",
        fontSize=10,
        fontName="Helvetica-Oblique",
        textColor=colors.Color(0.4, 0.4, 0.4),
        spaceAfter=12
    ))
    
    # Invoice Title
    styles.add(ParagraphStyle(
        name="InvoiceTitle",
        fontSize=20,
        fontName="Helvetica-Bold",
        textColor=colors.Color(0.2, 0.2, 0.2),
        alignment=TA_RIGHT,
        spaceAfter=6
    ))
    
    # Meta Info
    styles.add(ParagraphStyle(
        name="MetaInfo",
        fontSize=9,
        fontName="Helvetica",
        alignment=TA_RIGHT,
        textColor=colors.Color(0.3, 0.3, 0.3),
        leading=13
    ))
    
    # Section Header
    styles. add(ParagraphStyle(
        name="SectionHeader",
        fontSize=11,
        fontName="Helvetica-Bold",
        textColor=colors.Color(0.1, 0.1, 0.1),
        spaceAfter=8,
        spaceBefore=12,
        borderWidth=0,
        borderColor=colors.Color(0.2, 0.2, 0.2),
        borderPadding=4,
        backColor=colors.Color(0.95, 0.95, 0.95)
    ))
    
    # Table Header
    styles.add(ParagraphStyle(
        name="TableHeader",
        fontSize=9,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER
    ))
    
    # Footer Style
    styles.add(ParagraphStyle(
        name="FooterNote",
        fontSize=9,
        fontName="Helvetica-Oblique",
        textColor=colors.grey,
        alignment=TA_CENTER,
        spaceAfter=6
    ))

    elements = []

    # =====================================================
    # 📋 HEADER SECTION
    # =====================================================
    header_data = [
        [
            Paragraph("<b>SLAYDRIP</b><br/><font size=10><i>Premium Fashion Wear</i></font>", styles["BrandHeader"]),
            Paragraph(
                f"<b><font size=14>INVOICE</font></b><br/>"
                f"<b>Invoice No:</b> {invoice_no}<br/>"
                f"<b>Date:</b> {bill_date.strftime('%d %B %Y')}<br/>"
                f"<b>Bill No:</b> {bill_no}<br/>"
                f"<b>Payment Mode:</b> {payment_mode. upper()}",
                styles["MetaInfo"]
            )
        ]
    ]
    
    header_table = Table(header_data, colWidths=[100*mm, 70*mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ALIGN", (0,0), (0,0), "LEFT"),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
    ]))
    
    elements.append(header_table)
    
    # Decorative line
    elements.append(Spacer(1, 4))
    line_table = Table([["", ""]], colWidths=[170*mm])
    line_table.setStyle(TableStyle([
        ("LINEBELOW", (0,0), (-1,0), 2, colors.Color(0.2, 0.2, 0.2)),
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 16))

    # =====================================================
    # 👤 CUSTOMER DETAILS
    # =====================================================
    elements. append(Paragraph("BILL TO", styles["SectionHeader"]))
    
    customer_data = [
        ["Customer Name:", Paragraph(f"<b>{customer_name}</b>", styles["Normal"])],
        ["Phone Number:", Paragraph(f"<b>{phone}</b>", styles["Normal"])]
    ]
    
    customer_table = Table(customer_data, colWidths=[35*mm, 135*mm])
    customer_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.Color(0.95, 0.95, 0.95)),
        ("TEXTCOLOR", (0,0), (0,-1), colors.Color(0.3, 0.3, 0.3)),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("GRID", (0,0), (-1,-1), 0.5, colors.Color(0.8, 0.8, 0.8)),
    ]))
    
    elements.append(customer_table)
    elements.append(Spacer(1, 18))

    # =====================================================
    # 🛍️ ITEMS TABLE
    # =====================================================
    elements.append(Paragraph("ITEM DETAILS", styles["SectionHeader"]))
    
    # Table Header
    item_data = [[
        Paragraph("<b>PRODUCT</b>", styles["TableHeader"]),
        Paragraph("<b>SIZE</b>", styles["TableHeader"]),
        Paragraph("<b>QTY</b>", styles["TableHeader"]),
        Paragraph("<b>RATE (Rs.)</b>", styles["TableHeader"]),
        Paragraph("<b>AMOUNT (Rs. )</b>", styles["TableHeader"])
    ]]
    
    # Table Rows
    for idx, item in enumerate(cart):
        bg_color = colors.Color(0.98, 0.98, 0.98) if idx % 2 == 0 else colors.white
        item_data.append([
            Paragraph(item["design_text"], styles["Normal"]),
            Paragraph(f"<b>{item['size']}</b>", styles["Normal"]),
            Paragraph(f"<b>{item['quantity']}</b>", styles["Normal"]),
            Paragraph(f"Rs. {item['price']:.2f}", styles["Normal"]),
            Paragraph(f"<b>Rs. {item['price'] * item['quantity']:.2f}</b>", styles["Normal"])
        ])
    
    item_table = Table(item_data, colWidths=[78*mm, 18*mm, 15*mm, 28*mm, 31*mm])
    item_table.setStyle(TableStyle([
        # Header styling
        ("BACKGROUND", (0,0), (-1,0), colors.Color(0.2, 0.2, 0.2)),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 9),
        ("ALIGN", (0,0), (-1,0), "CENTER"),
        ("VALIGN", (0,0), (-1,0), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,0), 8),
        ("BOTTOMPADDING", (0,0), (-1,0), 8),
        
        # Body styling
        ("FONTSIZE", (0,1), (-1,-1), 9),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
        ("ALIGN", (3,1), (4,-1), "RIGHT"),
        ("VALIGN", (0,1), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,1), (-1,-1), 7),
        ("BOTTOMPADDING", (0,1), (-1,-1), 7),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        
        # Alternating row colors
        *[("BACKGROUND", (0,i), (-1,i), colors.Color(0.98, 0.98, 0.98)) 
          for i in range(1, len(item_data), 2)],
        
        # Grid
        ("GRID", (0,0), (-1,-1), 0.5, colors.Color(0.7, 0.7, 0.7)),
        ("LINEBELOW", (0,0), (-1,0), 1.5, colors.white),
    ]))
    
    elements.append(item_table)
    elements.append(Spacer(1, 20))

    # =====================================================
    # 💰 FINANCIAL SUMMARY (NEW LOGIC)
    # =====================================================
    summary_data = [
        ["Subtotal (Incl. GST)", f"Rs. {subtotal_inclusive:.2f}"],
        ["Base Price (Excl. GST)", f"Rs. {base_price_total:.2f}"],
        [f"Discount ({discount_percent}%)", f"- Rs. {discount_amount:.2f}"],
        ["Discounted Base Price", f"Rs. {discounted_base_price:.2f}"],
        [f"GST ({gst_percent}%)", f"+ Rs. {gst_amount:.2f}"],
    ]
    
    summary_table = Table(summary_data, colWidths=[50*mm, 35*mm], hAlign="RIGHT")
    summary_table.setStyle(TableStyle([
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ALIGN", (0,0), (0,-1), "LEFT"),
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.Color(0.2, 0.2, 0.2)),
        ("LINEBELOW", (0,-1), (-1,-1), 1, colors.Color(0.7, 0.7, 0.7)),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 4))
    
    # Grand Total
    grand_total_data = [[
        Paragraph("<b><font color='white'>GRAND TOTAL</font></b>", styles["Normal"]),
        Paragraph(f"<b><font color='white'>Rs. {grand_total:,.2f}</font></b>", styles["Normal"])
    ]]
    
    grand_total_table = Table(grand_total_data, colWidths=[50*mm, 35*mm], hAlign="RIGHT")
    grand_total_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.Color(0.2, 0.2, 0.2)),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 11),
        ("ALIGN", (0,0), (0,0), "LEFT"),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
    ]))
    
    elements.append(grand_total_table)
    elements.append(Spacer(1, 30))

    # =====================================================
    # 📝 FOOTER NOTES
    # =====================================================
    elements.append(Paragraph(
        "<b>Terms & Conditions: </b>",
        styles["SectionHeader"]
    ))
    
    terms = [
        "• All sales are final.  No refunds or exchanges.",
        "• Products sold are subject to our standard warranty terms.",
        "• Please retain this invoice for future reference.",
        "• All prices are inclusive of GST."
    ]
    
    for term in terms:
        elements.append(Paragraph(term, styles["FooterNote"]))
    
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph(
        "Thank you for shopping with <b>SLAYDRIP</b> – Your style, our passion!",
        styles["FooterNote"]
    ))

    # =====================================================
    # 🎨 BUILD PDF WITH CUSTOM CANVAS
    # =====================================================
    doc.build(elements, canvasmaker=InvoiceCanvas)

    # -------- SAVE SALE --------
    cursor. execute("""
        INSERT INTO sales
        (customer_name, phone, invoice_no, bill_no, bill_date,
         payment_mode, subtotal, discount_percent,
         discount_amount, gst_amount, total_amount, pdf_file)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        customer_name, phone, invoice_no, bill_no, bill_date,
        payment_mode, base_price_total, discount_percent,
        discount_amount, gst_amount, grand_total, pdf_filename
    ))

    conn.commit()
    cursor.close()
    conn.close()
    session.pop("cart", None)

    return render_template(
        "bill_template.html",
        pdf_file=pdf_filename,
        items=cart,
        customer_name=customer_name,
        phone=phone,
        invoice_no=invoice_no,
        bill_no=bill_no,
        bill_date=bill_date. strftime("%d-%m-%Y"),
        payment_mode=payment_mode,
        subtotal=subtotal_inclusive,
        base_price=base_price_total,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        discounted_subtotal=discounted_base_price,
        gst_percent=gst_percent,
        gst_amount=gst_amount,
        grand_total=grand_total
    )


# =====================================================
# DOWNLOAD PDF
# =====================================================
@app. route("/download/<filename>")
def download_pdf(filename):
    return send_from_directory(GENERATED_BILLS_DIR, filename, as_attachment=False)

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)
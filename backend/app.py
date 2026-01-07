# =====================================================
# IMPORTS
# =====================================================
from flask import Flask, render_template, request, session, jsonify, send_from_directory, redirect, url_for, flash
from datetime import date
from decimal import Decimal
import time, os, uuid
#from backend.db import get_connection
from db import get_connection
from psycopg2.extras import RealDictCursor
from functools import wraps

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

ALLOWED_PAYMENT_MODES = {"Cash", "UPI", "Card"}

# =====================================================
# LOGIN REQUIRED DECORATOR
# =====================================================
def login_required(f):
    """Decorator to protect routes that require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'staff_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def generate_ref(prefix: str) -> str:
    """Generate a short reference for returns/exchanges."""
    return f"{prefix}-{int(time.time())}-{uuid.uuid4().hex[:5].upper()}"


def load_returnable_items(cursor, invoice_no: str):
    """Fetch sold items with how many units are still returnable."""
    cursor.execute(
        """
        SELECT
            si.design_id,
            si.size,
            si.quantity AS sold_qty,
            si.price AS unit_price,
            d.design_code,
            d.product_name,
            d.color,
            COALESCE(r.total_returned, 0) AS already_returned
        FROM sale_items si
        JOIN designs d ON d.design_id = si.design_id
        LEFT JOIN (
            SELECT invoice_no, design_id, size, SUM(quantity) AS total_returned
            FROM returns
            WHERE invoice_no = %s
            GROUP BY invoice_no, design_id, size
        ) r
        ON r.invoice_no = si.invoice_no AND r.design_id = si.design_id AND r.size = si.size
        WHERE si.invoice_no = %s
        """,
        (invoice_no, invoice_no)
    )

    items = {}
    for row in cursor.fetchall():
        returnable = max(0, row["sold_qty"] - row["already_returned"])
        items[(row["design_id"], row["size"])] = {
            "design_id": row["design_id"],
            "size": row["size"],
            "sold_qty": row["sold_qty"],
            "unit_price": float(row["unit_price"]),
            "design_code": row["design_code"],
            "product_name": row["product_name"],
            "color": row["color"],
            "already_returned": row["already_returned"],
            "returnable": returnable
        }
    return items

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
        footer_text = "SLAYDRIP | Premium Fashion Wear | Contact(ig): salydrip.in| www.slaydrip.com"
        self.drawCentredString(A4[0]/2, 11*mm, footer_text)
        
        # Page number
        self.drawRightString(A4[0]-20*mm, 11*mm, f"Page {page_num} of {page_count}")
        
        self.restoreState()

# =====================================================
# LOGIN
# =====================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            return render_template("login.html", error="Please enter both username and password")
        
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT staff_id, username, password, full_name, is_active
            FROM staff
            WHERE username=%s
        """, (username,))
        
        staff = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if staff and staff["is_active"]:
            # Check plain text password
            if staff["password"] == password:
                session["staff_id"] = staff["staff_id"]
                session["staff_name"] = staff["full_name"]
                session["username"] = staff["username"]
                return redirect(url_for("home"))
        
        return render_template("login.html", error="Invalid username or password")
    
    # If already logged in, redirect to home
    if 'staff_id' in session:
        return redirect(url_for('home'))
    
    return render_template("login.html")

# =====================================================
# LOGOUT
# =====================================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# =====================================================
# UPDATE STALL LOCATION
# =====================================================
@app.route("/update-stall-location", methods=["POST"])
@login_required
def update_stall_location():
    stall_location = request.form.get("stall_location", "").strip()
    
    if not stall_location:
        return redirect(url_for("home"))
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE store_settings
        SET current_stall_location=%s
        WHERE id=1
    """, (stall_location,))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for("home"))

# =====================================================
# HOME
# =====================================================
@app.route("/")
@login_required
def home():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT design_id, design_code, product_name, gender, color, price
        FROM designs
    """)
    designs = cursor. fetchall()

    cursor.execute("SELECT discount_percent, current_stall_location FROM store_settings WHERE id=1")
    settings = cursor.fetchone()
    discount_percent = settings["discount_percent"]
    current_stall_location = settings.get("current_stall_location", "Main Store")

    cursor.close()
    conn.close()

    return render_template(
        "pos.html", 
        designs=designs, 
        discount_percent=discount_percent,
        current_stall_location=current_stall_location,
        staff_name=session.get("staff_name", "Unknown")
    )

# =====================================================
# GET SIZES
# =====================================================
@app.route("/get-sizes/<int:design_id>")
@login_required
def get_sizes(design_id):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT size, stock FROM design_stock
        WHERE design_id=%s
    """, (design_id,))

    sizes = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(sizes)

# =====================================================
# SAVE CART
# =====================================================
@app.route("/save-cart", methods=["POST"])
@login_required
def save_cart():
    session["cart"] = request.json. get("cart", [])
    session.modified = True
    return jsonify({"status": "saved"})

# =====================================================
# CHECKOUT
# =====================================================
@app.route("/checkout", methods=["POST"])
@login_required
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
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT gst_percent, current_stall_location FROM store_settings WHERE id=1")
    settings = cursor.fetchone()
    default_gst_percent = float(settings["gst_percent"])
    stall_location = settings.get("current_stall_location", "Main Store")
    
    # Get staff info from session
    staff_id = session.get("staff_id")
    staff_name = session.get("staff_name", "Unknown")

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
                f"<b>Staff:</b> {staff_name}<br/>"
                f"<b>Location:</b> {stall_location}<br/>"
                f"<b>Payment Mode:</b> {payment_mode.upper()}",
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
    cursor.execute("""
        INSERT INTO sales
        (customer_name, phone, invoice_no, bill_no, bill_date,
         payment_mode, subtotal, discount_percent,
         discount_amount, gst_amount, total_amount, pdf_file,
         staff_id, stall_location)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        customer_name, phone, invoice_no, bill_no, bill_date,
        payment_mode, base_price_total, discount_percent,
        discount_amount, gst_amount, grand_total, pdf_filename,
        staff_id, stall_location
    ))

    # -------- SAVE SALE ITEMS --------
    for item in cart:
        cursor.execute("""
            INSERT INTO sale_items
            (invoice_no, design_id, size, quantity, price)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            invoice_no,
            item['design_id'],
            item['size'],
            item['quantity'],
            item['price']
        ))
        
        # Update stock
        cursor.execute("""
            UPDATE design_stock
            SET stock = stock - %s
            WHERE design_id = %s AND size = %s
        """, (item['quantity'], item['design_id'], item['size']))

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
# RETURNS & EXCHANGES
# =====================================================
@app.route("/return-exchange")
@login_required
def return_exchange_page():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT design_id, design_code, product_name, color, gender, price
        FROM designs
        ORDER BY design_code
        """
    )
    designs = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        "return_exchange.html",
        designs=designs,
        staff_name=session.get("staff_name", "Unknown")
    )


@app.route("/api/invoice/<invoice_no>")
@login_required
def api_get_invoice(invoice_no):
    invoice_no = invoice_no.strip()
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute(
        """
        SELECT invoice_no, customer_name, phone, bill_date, payment_mode, total_amount
        FROM sales
        WHERE invoice_no=%s
        """,
        (invoice_no,)
    )
    sale = cursor.fetchone()
    if not sale:
        cursor.close()
        conn.close()
        return jsonify({"error": "Invoice not found"}), 404

    items = load_returnable_items(cursor, invoice_no)

    cursor.close()
    conn.close()

    return jsonify({
        "sale": sale,
        "items": list(items.values())
    })


@app.route("/api/returns", methods=["POST"])
@login_required
def api_process_return():
    payload = request.get_json(force=True) or {}
    invoice_no = (payload.get("invoice_no") or "").strip()
    payment_mode = (payload.get("payment_mode") or "").strip()
    items = payload.get("items") or []

    if not invoice_no:
        return jsonify({"error": "Invoice number is required"}), 400
    if payment_mode not in ALLOWED_PAYMENT_MODES:
        return jsonify({"error": "Invalid payment mode"}), 400
    if not items:
        return jsonify({"error": "No items selected"}), 400

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    def fail(message, status=400):
        conn.rollback()
        cursor.close(); conn.close()
        return jsonify({"error": message}), status

    try:
        cursor.execute("SELECT 1 FROM sales WHERE invoice_no=%s", (invoice_no,))
        if not cursor.fetchone():
            return fail("Invoice not found", 404)

        sold_items = load_returnable_items(cursor, invoice_no)
        if not sold_items:
            return fail("No items found for invoice")

        ref = generate_ref("RET")
        total_refund = Decimal("0.00")
        processed = []

        for item in items:
            try:
                design_id = int(item.get("design_id"))
                size = (item.get("size") or "").strip()
                qty = int(item.get("quantity"))
            except Exception:
                return fail("Invalid item payload")

            key = (design_id, size)
            if key not in sold_items:
                return fail(f"Item {design_id}-{size} not in invoice")

            allowed = sold_items[key]["returnable"]
            if qty <= 0 or qty > allowed:
                return fail(f"Invalid qty for {design_id}-{size}. Max {allowed}")

            unit_price = Decimal(str(sold_items[key]["unit_price"]))
            line_refund = unit_price * qty
            total_refund += line_refund

            cursor.execute(
                """
                UPDATE design_stock
                SET stock = stock + %s
                WHERE design_id=%s AND size=%s
                """,
                (qty, design_id, size)
            )
            if cursor.rowcount == 0:
                raise RuntimeError(f"Stock row missing for design {design_id} size {size}")

            cursor.execute(
                """
                INSERT INTO returns
                (return_ref, invoice_no, design_id, size, quantity, refund_amount, return_type, payment_mode)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (ref, invoice_no, design_id, size, qty, line_refund, "RETURN", payment_mode)
            )

            processed.append({
                "design_id": design_id,
                "size": size,
                "quantity": qty,
                "refund_amount": float(line_refund)
            })

        conn.commit()
        cursor.close(); conn.close()

        return jsonify({
            "return_ref": ref,
            "total_refund": float(total_refund),
            "items": processed
        })

    except Exception as exc:
        conn.rollback()
        cursor.close(); conn.close()
        return jsonify({"error": str(exc)}), 500


@app.route("/api/exchanges", methods=["POST"])
@login_required
def api_process_exchange():
    payload = request.get_json(force=True) or {}
    invoice_no = (payload.get("invoice_no") or "").strip()
    payment_mode = (payload.get("payment_mode") or "").strip()
    return_items = payload.get("return_items") or []
    new_items = payload.get("new_items") or []
    # Optional discount percent applied to new exchange items
    try:
        discount_percent = float(payload.get("discount_percent") or 0)
        if discount_percent < 0:
            discount_percent = 0.0
    except Exception:
        discount_percent = 0.0

    if not invoice_no:
        return jsonify({"error": "Invoice number is required"}), 400
    if payment_mode not in ALLOWED_PAYMENT_MODES:
        return jsonify({"error": "Invalid payment mode"}), 400
    if not return_items:
        return jsonify({"error": "At least one item must be returned"}), 400

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    def fail(message, status=400):
        conn.rollback()
        cursor.close(); conn.close()
        return jsonify({"error": message}), status

    try:
        cursor.execute("SELECT 1 FROM sales WHERE invoice_no=%s", (invoice_no,))
        if not cursor.fetchone():
            return fail("Invoice not found", 404)

        sold_items = load_returnable_items(cursor, invoice_no)
        if not sold_items:
            return fail("No items found for invoice")

        # Map design price for new items
        cursor.execute("SELECT design_id, price FROM designs")
        design_price_map = {row["design_id"]: Decimal(str(row["price"])) for row in cursor.fetchall()}

        exc_ref = generate_ref("EXC")
        returned_total = Decimal("0.00")
        new_total = Decimal("0.00")

        # Handle returned items first (stock + refund credit)
        for item in return_items:
            design_id = int(item.get("design_id"))
            size = (item.get("size") or "").strip()
            qty = int(item.get("quantity"))

            key = (design_id, size)
            if key not in sold_items:
                return fail(f"Item {design_id}-{size} not in invoice")

            allowed = sold_items[key]["returnable"]
            if qty <= 0 or qty > allowed:
                return fail(f"Invalid qty for {design_id}-{size}. Max {allowed}")

            unit_price = Decimal(str(sold_items[key]["unit_price"]))
            line_refund = unit_price * qty
            returned_total += line_refund

            cursor.execute(
                """
                UPDATE design_stock
                SET stock = stock + %s
                WHERE design_id=%s AND size=%s
                """,
                (qty, design_id, size)
            )
            if cursor.rowcount == 0:
                raise RuntimeError(f"Stock row missing for design {design_id} size {size}")

            cursor.execute(
                """
                INSERT INTO returns
                (return_ref, invoice_no, design_id, size, quantity, refund_amount, return_type, payment_mode)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (exc_ref, invoice_no, design_id, size, qty, line_refund, "EXCHANGE", payment_mode)
            )

        # Handle new items (stock - and record in exchange_details)
        for item in new_items:
            design_id = int(item.get("design_id"))
            size = (item.get("size") or "").strip()
            qty = int(item.get("quantity"))

            if qty <= 0:
                return fail("Quantity must be positive for new items")

            if design_id not in design_price_map:
                return fail(f"Design {design_id} not found")

            unit_price = design_price_map[design_id]

            cursor.execute(
                "SELECT stock FROM design_stock WHERE design_id=%s AND size=%s",
                (design_id, size)
            )
            row = cursor.fetchone()
            if not row:
                return fail(f"No stock row for {design_id}-{size}")
            if row["stock"] < qty:
                return fail(f"Insufficient stock for {design_id}-{size}")

            cursor.execute(
                """
                UPDATE design_stock
                SET stock = stock - %s
                WHERE design_id=%s AND size=%s
                """,
                (qty, design_id, size)
            )

            line_total = unit_price * qty
            new_total += line_total

            cursor.execute(
                """
                INSERT INTO exchange_details
                (exchange_ref, invoice_no, design_id, size, quantity, unit_price, line_total)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (exc_ref, invoice_no, design_id, size, qty, unit_price, line_total)
            )

        # Apply discount on new items total for settlement purpose
        discount_amount = (new_total * Decimal(str(discount_percent))) / Decimal("100")
        new_total_after_discount = new_total - discount_amount

        diff = returned_total - new_total_after_discount
        if diff > 0:
            settlement = {"type": "REFUND", "amount": float(diff)}
        elif diff < 0:
            settlement = {"type": "COLLECT", "amount": float(abs(diff))}
        else:
            settlement = {"type": "EVEN", "amount": 0.0}

        conn.commit()
        cursor.close(); conn.close()

        return jsonify({
            "exchange_ref": exc_ref,
            "returned_total": float(returned_total),
            "new_total": float(new_total),
            "discount_percent": discount_percent,
            "discount_amount": float(discount_amount),
            "settlement": settlement,
            "payment_mode": payment_mode
        })

    except Exception as exc:
        conn.rollback()
        cursor.close(); conn.close()
        return jsonify({"error": str(exc)}), 500


# =====================================================
# DOWNLOAD PDF
# =====================================================
@app.route("/download/<filename>")
@login_required
def download_pdf(filename):
    return send_from_directory(GENERATED_BILLS_DIR, filename, as_attachment=False)

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)
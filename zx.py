import streamlit as st
import sqlite3
import pandas as pd
import datetime
import os
import io

# مكتبات الرسوم البيانية PDF و Barcode و Plotly
import plotly.express as px
from fpdf import FPDF
import barcode
from barcode.writer import ImageWriter

# ----------------------------------------------------
# 1. إعدادات الصفحة والهوية البصرية باللون الذهبي
# ----------------------------------------------------
st.set_page_config(
    page_title="نظام الهاشمية للمبيعات والمخزون",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp {
        background-color: #0b0f19;
        color: #f8fafc;
    }
    h1, h2, h3, .stSidebar h1 {
        color: #f59e0b !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stButton>button {
        background-color: #d97706;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        border: none;
    }
    .stButton>button:hover {
        background-color: #f59e0b;
        color: black;
    }
    div[data-testid="stMetricValue"] {
        color: #f59e0b !important;
    }
    .gold-box {
        border: 2px solid #f59e0b;
        padding: 12px;
        border-radius: 10px;
        background-color: #111827;
        margin-bottom: 10px;
    }
    .welcome-card {
        border: 2px solid #d97706;
        background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
        padding: 30px;
        border-radius: 16px;
        text-align: center;
        box-shadow: 0 10px 25px rgba(245, 158, 11, 0.2);
        margin: auto;
        max-width: 500px;
    }
</style>
""", unsafe_allow_html=True)

DB_NAME = "al_hashemiah_pos.db"

# ----------------------------------------------------
# 2. إنشاء وتحديث قاعدة البيانات (الجداول الكاملة)
# ----------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            price REAL NOT NULL,
            cost_price REAL NOT NULL,
            stock INTEGER NOT NULL,
            min_stock INTEGER DEFAULT 5
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            customer_name TEXT,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total_price REAL NOT NULL,
            discount REAL DEFAULT 0.0,
            net_profit REAL NOT NULL,
            payment_method TEXT NOT NULL,
            seller_username TEXT DEFAULT 'admin'
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            notes TEXT,
            status TEXT DEFAULT 'غير مدفوع'
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            phone TEXT,
            points INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0.0,
            tier TEXT DEFAULT 'عادي'
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT
        )
    ''')
    
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", "admin123", "Admin"))
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("cashier1", "1234", "Cashier"))

    # إضافة زبون عام افتراضي
    c.execute("SELECT COUNT(*) FROM customers")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO customers (name, phone, points, total_spent, tier) VALUES (?, ?, ?, ?, ?)", ("زبون عام", "0700000000", 0, 0.0, "عادي"))
        
    conn.commit()
    conn.close()

init_db()

def log_action(username, action, details):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO audit_logs (timestamp, username, action, details) VALUES (?, ?, ?, ?)",
              (now_str, username, action, details))
    conn.commit()
    conn.close()

# توليد ملف PDF للفاتورة
def generate_pdf_invoice(invoice_id, cust_name, items, subtotal, discount, grand_total, pay_method):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Al-Hashemiah Store - Invoice", ln=True, align='C')
    
    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 8, txt=f"Invoice ID: #{invoice_id}", ln=True, align='R')
    pdf.cell(200, 8, txt=f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='R')
    pdf.cell(200, 8, txt=f"Customer: {cust_name}", ln=True, align='R')
    pdf.cell(200, 8, txt=f"Payment Method: {pay_method}", ln=True, align='R')
    pdf.ln(5)

    # جدول المنتجات
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(80, 8, "Product", 1, 0, 'C')
    pdf.cell(30, 8, "Qty", 1, 0, 'C')
    pdf.cell(40, 8, "Price", 1, 0, 'C')
    pdf.cell(40, 8, "Total", 1, 1, 'C')

    pdf.set_font("Arial", '', 10)
    for item in items:
        pdf.cell(80, 8, str(item['name']), 1, 0, 'L')
        pdf.cell(30, 8, str(item['quantity']), 1, 0, 'C')
        pdf.cell(40, 8, f"{item['price']:.2f}", 1, 0, 'C')
        pdf.cell(40, 8, f"{item['subtotal']:.2f}", 1, 1, 'C')

    pdf.ln(5)
    pdf.cell(200, 6, txt=f"Subtotal: {subtotal:.2f} JOD", ln=True, align='R')
    pdf.cell(200, 6, txt=f"Discount: {discount:.2f} JOD", ln=True, align='R')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 8, txt=f"Grand Total: {grand_total:.2f} JOD", ln=True, align='R')
    
    return pdf.output(dest='S').encode('latin1')

# دالة لتوليد صورة باركود حقيقية
def create_barcode_image(barcode_text):
    rv = io.BytesIO()
    Code128 = barcode.get_barcode_class('code128')
    code_instance = Code128(barcode_text, writer=ImageWriter())
    code_instance.write(rv)
    return rv.getvalue()

# ----------------------------------------------------
# 3. إدارة جلسة تسجيل الدخول
# ----------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "logged_user" not in st.session_state:
    st.session_state["logged_user"] = None
if "user_role" not in st.session_state:
    st.session_state["user_role"] = None
if "cart" not in st.session_state:
    st.session_state["cart"] = []

if not st.session_state["authenticated"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown("""
        <div class="welcome-card">
            <h1 style="color: #f59e0b; margin-bottom: 5px;">👑 متجر الهاشمية</h1>
            <h3 style="color: #f8fafc; font-size: 18px; margin-top: 0;">نظام المبيعات والمخزون الذكي متناهي الدقة</h3>
            <p style="color: #9ca3af; font-size: 13px;">يرجى تسجيل الدخول للبدء</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")

        with st.form("login_form"):
            username_input = st.text_input("👤 اسم المستخدم:")
            password_input = st.text_input("🔑 كلمة السر:", type="password")
            submit_login = st.form_submit_button("🔓 تسجيل الدخول", type="primary", use_container_width=True)
            
            if submit_login:
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("SELECT role FROM users WHERE username = ? AND password = ?", (username_input, password_input))
                user_match = c.fetchone()
                conn.close()

                if user_match:
                    st.session_state["authenticated"] = True
                    st.session_state["logged_user"] = username_input
                    st.session_state["user_role"] = user_match[0]
                    log_action(username_input, "تسجيل دخول", "تسجيل دخول ناجح")
                    st.rerun()
                else:
                    st.error("❌ اسم المستخدم أو كلمة السر غير صحيحة!")
    st.stop()

# ----------------------------------------------------
# 4. القائمة الجانبية ونظام الإشعارات الذكي (ميزة 3)
# ----------------------------------------------------
conn = sqlite3.connect(DB_NAME)
low_stock_count = pd.read_sql_query("SELECT COUNT(*) FROM products WHERE stock <= min_stock", conn).iloc[0,0]
unpaid_debts_count = pd.read_sql_query("SELECT COUNT(*) FROM debts WHERE status != 'تم التسديد'", conn).iloc[0,0]
conn.close()

st.sidebar.title("👑 متجر الهاشمية")
st.sidebar.markdown(f"👤 **المستخدم:** `{st.session_state['logged_user']}`")
st.sidebar.markdown(f"🛡️ **الصلاحية:** `{st.session_state['user_role']}`")

# تنبيهات الإشعارات في القائمة الجانبية
if low_stock_count > 0 or unpaid_debts_count > 0:
    st.sidebar.markdown(f"""
    <div style="background-color: #7f1d1d; border: 1px solid #ef4444; padding: 8px; border-radius: 8px; margin-bottom: 10px; font-size: 13px; text-align: center;">
        🔔 <b>تنبيهات النظام:</b><br>
        ⚠️ أصناف ناقصة: <b>{low_stock_count}</b><br>
        📙 ذمم غير مسددة: <b>{unpaid_debts_count}</b>
    </div>
    """, unsafe_allow_html=True)

if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
    st.session_state["authenticated"] = False
    st.rerun()

st.sidebar.write("---")

current_role = st.session_state.get("user_role", "Cashier")

if current_role == "Admin":
    menu_options = [
        "🛒 كاشير المبيعات (POS)",
        "📊 لوحة التحكّم الذكية (Dashboard)",
        "🚨 تنبيهات النقص وإعادة التزويد",
        "📙 سجل الذمم وتسديد الديون",
        "👥 إدارة العملاء وبرنامج الولاء (CRM)",
        "🔄 إرجاع واستبدال الفواتير",
        "📦 إدارة وتعديل المخزون والباركود",
        "🏷️ طباعة بطاقات الأسعار",
        "📜 سجل الأحداث والرقابة",
        "⚙️ النسخ الاحتياطي"
    ]
elif current_role == "Inventory":
    menu_options = [
        "📦 إدارة وتعديل المخزون والباركود",
        "🚨 تنبيهات النقص وإعادة التزويد",
        "🏷️ طباعة بطاقات الأسعار"
    ]
else:
    menu_options = [
        "🛒 كاشير المبيعات (POS)",
        "👥 إدارة العملاء وبرنامج الولاء (CRM)",
        "🔄 إرجاع واستبدال الفواتير",
        "📙 سجل الذمم وتسديد الديون"
    ]

menu = st.sidebar.radio("القائمة الرئيسية 🔱", menu_options)

def get_products():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()
    return df

# ----------------------------------------------------
# 1. كاشير المبيعات (مع دعم توليد PDF والفاتورة)
# ----------------------------------------------------
if menu == "🛒 كاشير المبيعات (POS)":
    st.header("🛒 نقطة البيع الذكية (POS)")
    df_products = get_products()

    conn = sqlite3.connect(DB_NAME)
    df_cust = pd.read_sql_query("SELECT name FROM customers", conn)
    conn.close()

    if df_products.empty:
        st.warning("⚠️ لا توجد منتجات بالمخزن.")
    else:
        col_scan, col_cart = st.columns([1.3, 1.1])

        with col_scan:
            st.subheader("📦 المنتجات المتاحة")
            barcode_scanner_input = st.text_input("🏷️ مسح الباركود السريع (Barcode Scanner):", placeholder="أدخل أو امسح الباركود هنا...")
            
            if barcode_scanner_input:
                matched_p = df_products[df_products["barcode"] == barcode_scanner_input]
                if not matched_p.empty:
                    prod = matched_p.iloc[0]
                    if prod['stock'] > 0:
                        existing_item = next((item for item in st.session_state["cart"] if item["id"] == prod['id']), None)
                        if existing_item:
                            existing_item['quantity'] += 1
                            existing_item['subtotal'] = existing_item['quantity'] * existing_item['price']
                            existing_item['profit'] = (existing_item['price'] - existing_item['cost_price']) * existing_item['quantity']
                        else:
                            st.session_state["cart"].append({
                                "id": prod['id'], "name": prod['name'], "price": prod['price'],
                                "cost_price": prod['cost_price'], "quantity": 1,
                                "subtotal": prod['price'], "profit": prod['price'] - prod['cost_price']
                            })
                        st.success(تم إضافة {prod['name']} بنجاح!)
                        st.rerun()

            search_query = st.text_input("🔎 تصفية بالاسم:", key="pos_search")
            filtered_df = df_products
            if search_query:
                filtered_df = df_products[df_products["name"].str.contains(search_query, case=False, na=False)]

            for idx, prod in filtered_df.iterrows():
                p1, p2, p3, p4 = st.columns([2.5, 1.2, 1.2, 1])
                p1.write(f"**{prod['name']}**\n`{prod['barcode']}`")
                p2.write(f"**{prod['price']:.2f} د.أ**")
                p3.write(f"رصيد: `{prod['stock']}`")
                if p4.button("➕ إضافة", key=f"add_{prod['id']}"):
                    if prod['stock'] > 0:
                        existing_item = next((item for item in st.session_state["cart"] if item["id"] == prod['id']), None)
                        if existing_item:
                            existing_item['quantity'] += 1
                            existing_item['subtotal'] = existing_item['quantity'] * existing_item['price']
                            existing_item['profit'] = (existing_item['price'] - existing_item['cost_price']) * existing_item['quantity']
                        else:
                            st.session_state["cart"].append({
                                "id": prod['id'], "name": prod['name'], "price": prod['price'],
                                "cost_price": prod['cost_price'], "quantity": 1,
                                "subtotal": prod['price'], "profit": prod['price'] - prod['cost_price']
                            })
                        st.rerun()
                st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)

        with col_cart:
            st.subheader("🛒 سلة المشتريات")
            if not st.session_state["cart"]:
                st.info("السلة فارغة.")
            else:
                for idx, item in enumerate(st.session_state["cart"]):
                    c1, c2, c3, c4 = st.columns([2, 1.5, 1.2, 0.6])
                    c1.write(f"**{item['name']}**")
                    new_q = c2.number_input("الكمية", min_value=1, value=int(item['quantity']), key=f"q_{idx}", label_visibility="collapsed")
                    if new_q != item['quantity']:
                        item['quantity'] = new_q
                        item['subtotal'] = new_q * item['price']
                        item['profit'] = (item['price'] - item['cost_price']) * new_q
                        st.rerun()
                    c3.write(f"**{item['subtotal']:.2f} د.أ**")
                    if c4.button("❌", key=f"del_{idx}"):
                        st.session_state["cart"].pop(idx)
                        st.rerun()

                st.write("---")
                subtotal_val = sum(item['subtotal'] for item in st.session_state["cart"])
                
                cust_name = st.selectbox("👤 اسم الزبون (العميل):", df_cust["name"].tolist())
                disc_val = st.number_input("قيمة الخصم (د.أ):", min_value=0.0, max_value=float(subtotal_val), value=0.0)
                grand_total = subtotal_val - disc_val
                
                st.markdown(f"### 💳 الصافي المطلوب: `{grand_total:.2f} د.أ`")
                pay_method = st.radio("طريقة الدفع:", ["نقداً (Cash)", "بطاقة (Card)", "ذمم / دين"], horizontal=True)

                if st.button("✅ إتمام عملية البيع وتحميل الفاتورة PDF", type="primary", use_container_width=True):
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    seller = st.session_state.get("logged_user", "admin")
                    
                    for item in st.session_state["cart"]:
                        item_profit = item['profit'] - (disc_val / len(st.session_state["cart"]))
                        c.execute("""
                            INSERT INTO sales (date, customer_name, product_name, quantity, total_price, discount, net_profit, payment_method, seller_username)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (now_str, cust_name, item['name'], item['quantity'], item['subtotal'], disc_val, item_profit, pay_method, seller))
                        c.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item['quantity'], item['id']))
                    
                    if pay_method == "ذمم / دين":
                        c.execute("INSERT INTO debts (customer_name, amount, date, notes, status) VALUES (?, ?, ?, ?, ?)", 
                                  (cust_name, grand_total, now_str, f"فاتورة مبيعات بتاريخ {now_str}", "غير مدفوع"))

                    # تحديث إجمالي المشتريات ونقاط الزبون (برنامج الولاء - ميزة 5)
                    c.execute("UPDATE customers SET total_spent = total_spent + ?, points = points + ? WHERE name = ?", 
                              (grand_total, int(grand_total), cust_name))
                    
                    conn.commit()
                    
                    # جلب رقم الفاتورة الأخيرة
                    c.execute("SELECT last_insert_rowid()")
                    last_inv_id = c.fetchone()[0]
                    conn.close()

                    log_action(seller, "بيع", f"فاتورة #{last_inv_id} بقيمة {grand_total:.2f} د.أ للزبون {cust_name}")
                    
                    # توليد ملف PDF
                    pdf_bytes = generate_pdf_invoice(last_inv_id, cust_name, st.session_state["cart"], subtotal_val, disc_val, grand_total, pay_method)
                    
                    st.success("🎉 تمت عملية البيع بنجاح!")
                    st.download_button(
                        label="📥 تحميل فاتورة المبيعات الرسمية (PDF)",
                        data=pdf_bytes,
                        file_name=f"Invoice_{last_inv_id}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
                    st.session_state["cart"] = []

# ----------------------------------------------------
# 2. لوحة التحكم الذكية والرسوم البيانية المتقدمة (ميزة 1 - Plotly)
# ----------------------------------------------------
elif menu == "📊 لوحة التحكّم الذكية (Dashboard)":
    st.header("📊 لوحة المؤشرات والرسوم البيانية التفاعلية (Advanced Dashboard)")
    
    conn = sqlite3.connect(DB_NAME)
    df_sales = pd.read_sql_query("SELECT * FROM sales", conn)
    conn.close()

    if df_sales.empty:
        st.info("💡 لا توجد بيانات مبيعات كافية لعرض لوحة التحكّم.")
    else:
        df_sales['date'] = pd.to_datetime(df_sales['date'])
        df_sales['hour'] = df_sales['date'].dt.hour
        df_sales['day_name'] = df_sales['date'].dt.day_name()
        df_sales['month_year'] = df_sales['date'].dt.to_period('M').astype(str)

        # مقارنة الأرباح بين الشهر الحالي والسابق
        current_month = datetime.datetime.now().strftime("%Y-%m")
        prev_month = (datetime.datetime.now().replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
        
        curr_profit = df_sales[df_sales['month_year'] == current_month]['net_profit'].sum()
        prev_profit = df_sales[df_sales['month_year'] == prev_month]['net_profit'].sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("أرباح الشهر الحالي", f"{curr_profit:.2f} د.أ", f"{curr_profit - prev_profit:.2f} مقارنة بالشهر السابق")
        m2.metric("إجمالي المبيعات", f"{df_sales['total_price'].sum():.2f} د.أ")
        m3.metric("صافي الأرباح العام", f"{df_sales['net_profit'].sum():.2f} د.أ")

        st.divider()

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("⏰ حركة المبيعات حسب ساعات اليوم")
            hourly_sales = df_sales.groupby("hour")["total_price"].sum().reset_index()
            fig_hour = px.bar(hourly_sales, x="hour", y="total_price", labels={"hour": "الساعة", "total_price": "المبيعات (د.أ)"}, color_discrete_sequence=["#d97706"])
            st.plotly_chart(fig_hour, use_container_width=True)

        with col_g2:
            st.subheader("📅 حركة المبيعات حسب أيام الأسبوع")
            daily_sales = df_sales.groupby("day_name")["total_price"].sum().reset_index()
            fig_day = px.pie(daily_sales, names="day_name", values="total_price", hole=0.4, color_discrete_sequence=px.colors.sequential.Sunset)
            st.plotly_chart(fig_day, use_container_width=True)

        st.divider()
        st.subheader("📈 توقع حركة استهلاك المواد (تحليل المخزون)")
        df_prods = get_products()
        if not df_prods.empty:
            sales_speed = df_sales.groupby("product_name")["quantity"].sum().reset_index()
            sales_speed.columns = ["اسم المنتج", "إجمالي المباع"]
            merged_stock = pd.merge(df_prods, sales_speed, left_on="name", right_on="اسم المنتج", how="left").fillna(0)
            merged_stock['حالة النفاد المتوقع'] = merged_stock.apply(lambda r: "🚨 خطر النفاد قريباً" if r['stock'] <= r['min_stock'] else "✅ مستقر", axis=1)
            st.dataframe(merged_stock[["name", "stock", "min_stock", "إجمالي المباع", "حالة النفاد المتوقع"]], use_container_width=True, hide_index=True)

# ----------------------------------------------------
# 3. تنبيهات النقص وإعادة التزويد
# ----------------------------------------------------
elif menu == "🚨 تنبيهات النقص وإعادة التزويد":
    st.header("🚨 مراقبة النقص وإعادة الشحن")
    conn = sqlite3.connect(DB_NAME)
    df_low = pd.read_sql_query("SELECT id, barcode, name, category, stock, min_stock FROM products WHERE stock <= min_stock", conn)
    conn.close()

    if df_low.empty:
        st.success("✅ جميع الأصناف متوفرة بأرصدة آمنة!")
    else:
        st.error(f"⚠️ يوجد ({len(df_low)}) منتجات وصلت لحد الأمان أو أقل!")
        st.dataframe(df_low, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# 4. سجل الذمم وتسديد الديون
# ----------------------------------------------------
elif menu == "📙 سجل الذمم وتسديد الديون":
    st.header("📙 متابعة وتسديد الديون والذمم")
    conn = sqlite3.connect(DB_NAME)
    df_debts = pd.read_sql_query("SELECT * FROM debts", conn)
    conn.close()

    if df_debts.empty:
        st.info("💡 لا توجد ديون مسجلة حالياً.")
    else:
        st.dataframe(df_debts, use_container_width=True, hide_index=True)
        unpaid = df_debts[df_debts["status"] != "تم التسديد"]
        if not unpaid.empty:
            d_id = st.selectbox("اختر الدين للتسديد:", unpaid["id"].tolist(), format_func=lambda x: f"#{x} - {unpaid[unpaid['id']==x]['customer_name'].values[0]}")
            curr_d = unpaid[unpaid["id"] == d_id].iloc[0]
            pay_amt = st.number_input("المبلغ المدفوع:", min_value=0.1, max_value=float(curr_d["amount"]), value=float(curr_d["amount"]))
            if st.button("💳 تسديد الدفعة"):
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                rem = curr_d["amount"] - pay_amt
                if rem <= 0:
                    c.execute("UPDATE debts SET amount = 0, status = 'تم التسديد' WHERE id = ?", (d_id,))
                else:
                    c.execute("UPDATE debts SET amount = ? WHERE id = ?", (rem, d_id))
                conn.commit()
                conn.close()
                st.success("تم التسديد بنجاح!")
                st.rerun()

# ----------------------------------------------------
# 5. إدارة العملاء وبرنامج الولاء (ميزة 5 - CRM)
# ----------------------------------------------------
elif menu == "👥 إدارة العملاء وبرنامج الولاء (CRM)":
    st.header("👥 مركز إدارة العملاء وبرنامج الولاء النقاط والخصومات")
    
    tab_add, tab_view = st.tabs(["➕ إضافة عميل جديد", "📋 قائمة العملاء والولاء"])
    
    with tab_add:
        with st.form("add_cust_form", clear_on_submit=True):
            c_name = st.text_input("اسم العميل:")
            c_phone = st.text_input("رقم الهاتق:")
            c_tier = st.selectbox("الفئة / التصنيف:", ["عادي", "برونزي", "فضي", "ذهبي (VIP)"])
            if st.form_submit_button("💾 حفظ العميل", type="primary"):
                if c_name:
                    try:
                        conn = sqlite3.connect(DB_NAME)
                        c = conn.cursor()
                        c.execute("INSERT INTO customers (name, phone, tier) VALUES (?, ?, ?)", (c_name, c_phone, c_tier))
                        conn.commit()
                        conn.close()
                        st.success("تم إضافة العميل بنجاح!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("اسم العميل موجود مسبقاً!")

    with tab_view:
        conn = sqlite3.connect(DB_NAME)
        df_customers = pd.read_sql_query("SELECT * FROM customers", conn)
        conn.close()
        st.dataframe(df_customers, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# 6. إرجاع واستبدال الفواتير (مع توليد سند PDF)
# ----------------------------------------------------
elif menu == "🔄 إرجاع واستبدال الفواتير":
    st.header("🔄 قسم استرجاع الفواتير")
    conn = sqlite3.connect(DB_NAME)
    df_sales = pd.read_sql_query("SELECT * FROM sales ORDER BY id DESC", conn)
    conn.close()

    if df_sales.empty:
        st.info("لا توجد مبيعات لإرجاعها.")
    else:
        search_inv = st.text_input("ابحث برقم الفاتورة أو اسم العميل:")
        filtered = df_sales
        if search_inv:
            filtered = df_sales[df_sales['id'].astype(str).str.contains(search_inv) | df_sales['customer_name'].str.contains(search_inv, na=False)]
        st.dataframe(filtered, use_container_width=True, hide_index=True)

        if not filtered.empty:
            sel_id = st.selectbox("اختر رقم الفاتورة للإرجاع:", filtered["id"].tolist())
            row = df_sales[df_sales["id"] == sel_id].iloc[0]
            ret_q = st.number_input("الكمية المرتجعة:", min_value=1, max_value=int(row['quantity']), value=int(row['quantity']))
            
            unit_p = row['total_price'] / row['quantity']
            refund_val = ret_q * unit_p

            if st.button("🔄 تأكيد الإرجاع", type="primary"):
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("UPDATE products SET stock = stock + ? WHERE name = ?", (ret_q, row['product_name']))
                if ret_q == row['quantity']:
                    c.execute("DELETE FROM sales WHERE id = ?", (sel_id,))
                else:
                    new_q = row['quantity'] - ret_q
                    c.execute("UPDATE sales SET quantity = ?, total_price = ? WHERE id = ?", (new_q, new_q * unit_p, sel_id))
                conn.commit()
                conn.close()
                st.success(f"تم إرجاع {ret_q} قطعة واسترداد {refund_val:.2f} د.أ للعميل!")

# ----------------------------------------------------
# 7. إدارة وتعديل المخزون مع توليد الباركود الحقيقي (ميزة 4)
# ----------------------------------------------------
elif menu == "📦 إدارة وتعديل المخزون والباركود":
    st.header("📦 إدارة المنتجات وتوليد الباركود الحقيقي")
    
    tab1, tab2 = st.tabs(["➕ إضافة صنف جديد", "🏷️ عرض الباركود وطباعته"])
    
    with tab1:
        with st.form("add_p_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                p_code = st.text_input("رمز الباركود (مثال: 123456789):")
                p_name = st.text_input("اسم المنتج:")
            with c2:
                p_cat = st.text_input("التصنيف:", value="عام")
                p_price = st.number_input("سعر البيع (د.أ):", min_value=0.01)
            with c3:
                p_cost = st.number_input("سعر التكلفة (د.أ):", min_value=0.0)
                p_stock = st.number_input("الكمية المتاحة:", min_value=1, value=10)

            if st.form_submit_button("💾 حفظ الصنف", type="primary"):
                if p_code and p_name:
                    try:
                        conn = sqlite3.connect(DB_NAME)
                        c = conn.cursor()
                        c.execute("INSERT INTO products (barcode, name, category, price, cost_price, stock) VALUES (?, ?, ?, ?, ?, ?)",
                                  (p_code, p_name, p_cat, p_price, p_cost, p_stock))
                        conn.commit()
                        conn.close()
                        st.success("تم إضافة الصنف بنجاح وتوليد باركود له!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("الباركود مستخدم مسبقاً!")

    with tab2:
        df_prods = get_products()
        if not df_prods.empty:
            selected_barcode_prod = st.selectbox("اختر المنتج لعرض باركود الحقيقي:", df_prods["name"].tolist())
            prod_row = df_prods[df_prods["name"] == selected_barcode_prod].iloc[0]
            
            st.write(f"**المنتج:** {prod_row['name']} | **الباركود:** `{prod_row['barcode']}`")
            try:
                barcode_bytes = create_barcode_image(str(prod_row['barcode']))
                st.image(barcode_bytes, caption=f"Barcode for {prod_row['name']}")
                st.download_button("📥 تحميل صورة الباركود", data=barcode_bytes, file_name=f"Barcode_{prod_row['barcode']}.png", mime="image/png")
            except Exception as e:
                st.error(f"خطأ في توليد الباركود: تأكد من أن الرمز أرقام أو حروف إنجليزية صحيحة. ({e})")

# ----------------------------------------------------
# 8. طباعة بطاقات الأسعار المصممة
# ----------------------------------------------------
elif menu == "🏷️ طباعة بطاقات الأسعار":
    st.header("🏷️ طباعة بطاقات الأسعار لرفوف المتجر")
    df_products = get_products()
    if not df_products.empty:
        sel_p = st.selectbox("اختر المنتج لطباعة بطاقته:", df_products["name"].tolist())
        p_data = df_products[df_products["name"] == sel_p].iloc[0]
        
        tag_html = f"""
        <div style="border: 2px solid #d97706; background: #111827; padding: 20px; border-radius: 12px; width: 300px; text-align: center; color: white; margin: auto;">
            <h3 style="color: #f59e0b; margin:0;">👑 متجر الهاشمية</h3>
            <h2 style="color: white; margin: 10px 0;">{p_data['name']}</h2>
            <div style="background: #1f2937; padding: 10px; border-radius: 8px;">
                <span style="color: #10b981; font-size: 32px; font-weight: bold;">{p_data['price']:.2f}</span> د.أ
            </div>
            <p style="color: #9ca3af; font-size: 11px; margin-top:8px;">Barcode: {p_data['barcode']}</p>
        </div>
        """
        st.markdown(tag_html, unsafe_allow_html=True)
        st.download_button("🖨️ طباعة البطاقة (HTML)", data=f"<html><body onload='window.print();'>{tag_html}</body></html>", file_name=f"Tag_{p_data['id']}.html", mime="text/html")

# ----------------------------------------------------
# 9. سجل الأحداث والرقابة (Audit Log)
# ----------------------------------------------------
elif menu == "📜 سجل الأحداث والرقابة":
    st.header("📜 سجل الرقابة الأمنية")
    conn = sqlite3.connect(DB_NAME)
    st.dataframe(pd.read_sql_query("SELECT * FROM audit_logs ORDER BY id DESC", conn), use_container_width=True, hide_index=True)
    conn.close()

# ----------------------------------------------------
# 10. النسخ الاحتياطي للنظام
# ----------------------------------------------------
elif menu == "⚙️ النسخ الاحتياطي":
    st.header("⚙️ النسخ الاحتياطي للقاعدة")
    with open(DB_NAME, "rb") as f:
        st.download_button("💾 تحميل نسخة `.db`", data=f, file_name=f"Backup_{datetime.date.today()}.db", mime="application/x-sqlite3", type="primary", use_container_width=True)
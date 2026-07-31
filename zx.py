import datetime
import io
import os
import sqlite3
import urllib.parse
import barcode
from barcode.writer import ImageWriter
from fpdf import FPDF
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ----------------------------------------------------
# 1. إعدادات الصفحة والهوية البصرية
# ----------------------------------------------------
st.set_page_config(
    page_title="نظام إدارة المبيعات والمخزون - مشروع التخرج",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
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
    .product-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        padding: 12px;
        border-radius: 10px;
        margin-bottom: 8px;
    }
</style>
""",
    unsafe_allow_html=True,
)

DB_NAME = "graduation_project_pos.db"


# ----------------------------------------------------
# 2. إنشاء وتحديث قاعدة البيانات
# ----------------------------------------------------
def init_db():
  conn = sqlite3.connect(DB_NAME)
  c = conn.cursor()

  c.execute("""
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
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            customer_name TEXT,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total_price REAL NOT NULL,
            discount REAL DEFAULT 0.0,
            net_profit REAL NOT NULL,
            seller_username TEXT DEFAULT 'admin',
            payment_type TEXT DEFAULT 'نقدي'
        )
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            phone TEXT,
            points INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0.0,
            debt REAL DEFAULT 0.0,
            tier TEXT DEFAULT 'عادي'
        )
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            notes TEXT
        )
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            supplier_name TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total_cost REAL NOT NULL
        )
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT
        )
    """)

  c.execute("SELECT COUNT(*) FROM users")
  if c.fetchone()[0] == 0:
    c.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        ("admin", "123", "مدير النظام"),
    )
    c.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        ("cashier", "123", "موظف مبيعات"),
    )

  c.execute("SELECT COUNT(*) FROM customers")
  if c.fetchone()[0] == 0:
    c.execute(
        "INSERT INTO customers (name, phone, points, total_spent, debt, tier)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        ("زبون عام", "0700000000", 0, 0.0, 0.0, "عادي"),
    )

  conn.commit()
  conn.close()


init_db()


def log_action(username, action, details):
  conn = sqlite3.connect(DB_NAME)
  c = conn.cursor()
  now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  c.execute(
      "INSERT INTO audit_logs (timestamp, username, action, details) VALUES"
      " (?, ?, ?, ?)",
      (now_str, username, action, details),
  )
  conn.commit()
  conn.close()


def generate_pdf_invoice(
    invoice_id, cust_name, items, subtotal, discount, grand_total
):
  pdf = FPDF()
  pdf.add_page()
  pdf.set_font("Arial", "B", 16)
  pdf.cell(200, 10, txt="Graduation Project Store - Invoice", ln=True, align="C")

  pdf.set_font("Arial", "", 12)
  pdf.cell(200, 8, txt=f"Invoice ID: #{invoice_id}", ln=True, align="R")
  pdf.cell(
      200,
      8,
      txt=f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
      ln=True,
      align="R",
  )
  pdf.cell(200, 8, txt=f"Customer: {cust_name}", ln=True, align="R")
  pdf.ln(5)

  pdf.set_font("Arial", "B", 10)
  pdf.cell(80, 8, "Product", 1, 0, "C")
  pdf.cell(30, 8, "Qty", 1, 0, "C")
  pdf.cell(40, 8, "Price", 1, 0, "C")
  pdf.cell(40, 8, "Total", 1, 1, "C")

  pdf.set_font("Arial", "", 10)
  for item in items:
    pdf.cell(80, 8, str(item["name"]), 1, 0, "L")
    pdf.cell(30, 8, str(item["quantity"]), 1, 0, "C")
    pdf.cell(40, 8, f"{item['price']:.2f}", 1, 0, "C")
    pdf.cell(40, 8, f"{item['subtotal']:.2f}", 1, 1, "C")

  pdf.ln(5)
  pdf.cell(200, 6, txt=f"Subtotal: {subtotal:.2f} JOD", ln=True, align="R")
  pdf.cell(200, 6, txt=f"Discount: {discount:.2f} JOD", ln=True, align="R")
  pdf.set_font("Arial", "B", 12)
  pdf.cell(
      200, 8, txt=f"Grand Total: {grand_total:.2f} JOD", ln=True, align="R"
  )

  return pdf.output(dest="S").encode("latin1")


def create_barcode_image(barcode_text):
  rv = io.BytesIO()
  Code128 = barcode.get_barcode_class("code128")
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
    st.markdown(
        """
        <div class="welcome-card">
            <h1 style="color: #f59e0b; margin-bottom: 5px;">👑 نظام إدارة المبيعات</h1>
            <h3 style="color: #f8fafc; font-size: 18px; margin-top: 0;">مشروع التخرج الأكاديمي الذكي</h3>
            <p style="color: #9ca3af; font-size: 13px;">يرجى تسجيل الدخول للبدء</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    with st.form("login_form"):
      username_input = st.text_input("👤 اسم المستخدم:")
      password_input = st.text_input("🔑 كلمة السر:", type="password")
      submit_login = st.form_submit_button(
          "🔓 تسجيل الدخول", type="primary", use_container_width=True
      )

      if submit_login:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            "SELECT role FROM users WHERE username = ? AND password = ?",
            (username_input, password_input),
        )
        user_match = c.fetchone()
        conn.close()

        if user_match:
          st.session_state["authenticated"] = True
          st.session_state["logged_user"] = username_input
          st.session_state["user_role"] = user_match[0]
          log_action(username_input, "تسجيل دخول", "تسجيل دخول ناجح للنظام")
          st.rerun()
        else:
          st.error("❌ اسم المستخدم أو كلمة السر غير صحيحة!")
  st.stop()

# ----------------------------------------------------
# 4. الشريط الجانبي والأدوات المتقدمة
# ----------------------------------------------------
conn = sqlite3.connect(DB_NAME)
low_stock_count = pd.read_sql_query(
    "SELECT COUNT(*) FROM products WHERE stock <= min_stock", conn
).iloc[0, 0]
conn.close()

st.sidebar.title("👑 لوحة التحكم الرئيسية")
st.sidebar.markdown(f"👤 **المستخدم:** `{st.session_state['logged_user']}`")
st.sidebar.markdown(f"🛡️ **الصلاحية:** `{st.session_state['user_role']}`")

with st.sidebar.expander("💱 محول العملات السريع"):
  currency_choice = st.selectbox(
      "العملة المعروضة:", ["دينار أردني (JOD)", "دولار أمريكي (USD)"]
  )
  exchange_rate = 1.41 if "USD" in currency_choice else 1.0

if low_stock_count > 0:
  st.sidebar.markdown(
      f"""
    <div style="background-color: #7f1d1d; border: 1px solid #ef4444; padding: 8px; border-radius: 8px; margin-bottom: 10px; font-size: 13px; text-align: center;">
        🔔 <b>تنبيهات النظام:</b><br>
        ⚠️ منتجات وصلت للحد الأدنى: <b>{low_stock_count}</b>
    </div>
    """,
      unsafe_allow_html=True,
  )

if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
  st.session_state["authenticated"] = False
  st.rerun()

st.sidebar.write("---")

current_role = st.session_state.get("user_role", "موظف مبيعات")

if current_role == "مدير النظام":
  menu_options = [
      "🛒 كاشير المبيعات (POS)",
      "📊 لوحة المؤشرات الذكية",
      "🤖 التنبؤ الذكي بالمبيعات (AI)",
      "📖 إدارة الديون والذمم المالية",
      "🚨 تنبيهات نقص المخزون",
      "👥 إدارة العملاء وبرنامج الولاء (CRM)",
      "📦 إدارة المنتجات وتوليد الباركود",
      "💸 المصروفات والنثريات المالية",
      "🚚 طلبات الموردين والشراء",
      "📈 أرباح المنتجات والتقارير",
      "⚙️ إدارة المستخدمين والصلاحيات",
      "📜 سجل الرقابة الأمنية (Audit Log)",
      "💾 النسخ الاحتياطي",
  ]
else:
  menu_options = [
      "🛒 كاشير المبيعات (POS)",
      "📖 إدارة الديون والذمم المالية",
      "👥 إدارة العملاء وبرنامج الولاء (CRM)",
      "📦 إدارة المنتجات وتوليد الباركود",
  ]

menu = st.sidebar.radio("الأقسام المتاحة 🔱", menu_options)


def get_products():
  conn = sqlite3.connect(DB_NAME)
  df = pd.read_sql_query("SELECT * FROM products", conn)
  conn.close()
  return df


# ----------------------------------------------------
# 1. كاشير المبيعات (POS)
# ----------------------------------------------------
if menu == "🛒 كاشير المبيعات (POS)":
  st.header("🛒 نقطة البيع الذكية (POS)")
  df_products = get_products()

  conn = sqlite3.connect(DB_NAME)
  df_cust = pd.read_sql_query("SELECT name, phone FROM customers", conn)
  conn.close()

  if df_products.empty:
    st.warning("⚠️ لا توجد منتجات مسجلة بالمخزن حالياً.")
  else:
    col_scan, col_cart = st.columns([1.3, 1.1])

    with col_scan:
      st.subheader("📦 المنتجات المتاحة")
      scanner_input = st.text_input(
          "🏷️ مسح الباركود السريع:", placeholder="أدخل أو امسح الباركود..."
      )

      if scanner_input:
        matched_p = df_products[df_products["barcode"] == scanner_input]
        if not matched_p.empty:
          prod = matched_p.iloc[0]
          if prod["stock"] > 0:
            existing_item = next(
                (
                    item
                    for item in st.session_state["cart"]
                    if item["id"] == prod["id"]
                ),
                None,
            )
            if existing_item:
              existing_item["quantity"] += 1
              existing_item["subtotal"] = (
                  existing_item["quantity"] * existing_item["price"]
              )
              existing_item["profit"] = (
                  existing_item["price"] - existing_item["cost_price"]
              ) * existing_item["quantity"]
            else:
              st.session_state["cart"].append({
                  "id": prod["id"],
                  "name": prod["name"],
                  "price": prod["price"],
                  "cost_price": prod["cost_price"],
                  "quantity": 1,
                  "subtotal": prod["price"],
                  "profit": prod["price"] - prod["cost_price"],
              })
            st.success(f"تم إضافة {prod['name']} للسلة بنجاح!")
            st.rerun()

      search_query = st.text_input("🔎 بحث عن منتج بالاسم:")
      filtered_df = df_products
      if search_query:
        filtered_df = df_products[
            df_products["name"].str.contains(search_query, case=False, na=False)
        ]

      # عرض المنتجات في بطاقات مرتبة ومنسقة بشكل جميل
      for idx, prod in filtered_df.iterrows():
        st.markdown(
            f"""
            <div class="product-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <b style="font-size: 16px; color: #f59e0b;">{prod['name']}</b><br>
                        <span style="color: #9ca3af; font-size: 12px;">الباركود: {prod['barcode']} | المخزن: <b style="color: #38bdf8;">{prod['stock']}</b></span>
                    </div>
                    <div style="text-align: left;">
                        <span style="font-size: 16px; font-weight: bold; color: #34d399;">{prod['price'] * exchange_rate:.2f} د.أ</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # زر الإضافة منفصل بدقة لضمان عدم حدوث تداخل
        if st.button("➕ إضافة للسلة", key=f"add_btn_{prod['id']}"):
          if prod["stock"] > 0:
            existing_item = next(
                (
                    item
                    for item in st.session_state["cart"]
                    if item["id"] == prod["id"]
                ),
                None,
            )
            if existing_item:
              existing_item["quantity"] += 1
              existing_item["subtotal"] = (
                  existing_item["quantity"] * existing_item["price"]
              )
              existing_item["profit"] = (
                  existing_item["price"] - existing_item["cost_price"]
              ) * existing_item["quantity"]
            else:
              st.session_state["cart"].append({
                  "id": prod["id"],
                  "name": prod["name"],
                  "price": prod["price"],
                  "cost_price": prod["cost_price"],
                  "quantity": 1,
                  "subtotal": prod["price"],
                  "profit": prod["price"] - prod["cost_price"],
              })
            st.rerun()
          else:
            st.error("نفذت الكمية من المخزن!")
        st.write("")

    with col_cart:
      st.subheader("🛒 سلة المشتريات الحالية")
      if not st.session_state["cart"]:
        st.info("السلة فارغة.")
      else:
        for idx, item in enumerate(st.session_state["cart"]):
          c1, c2, c3, c4 = st.columns([2, 1.5, 1.2, 0.6])
          c1.write(f"**{item['name']}**")
          new_q = c2.number_input(
              "الكمية",
              min_value=1,
              value=int(item["quantity"]),
              key=f"q_{idx}",
              label_visibility="collapsed",
          )
          if new_q != item["quantity"]:
            item["quantity"] = new_q
            item["subtotal"] = new_q * item["price"]
            item["profit"] = (item["price"] - item["cost_price"]) * new_q
            st.rerun()
          c3.write(f"**{item['subtotal'] * exchange_rate:.2f}**")
          if c4.button("❌", key=f"del_{idx}"):
            st.session_state["cart"].pop(idx)
            st.rerun()

        st.write("---")
        subtotal_val = sum(item["subtotal"] for item in st.session_state["cart"])

        cust_name = st.selectbox(
            "👤 اسم الزبون:", df_cust["name"].tolist()
        )
        pay_type = st.radio(
            "طريقة الدفع:", ["نقدي (Cash)", "آجل (تسجيل ذمم)"], horizontal=True
        )

        disc_val = st.number_input(
            "قيمة الخصم:", min_value=0.0, max_value=float(subtotal_val), value=0.0
        )
        grand_total = subtotal_val - disc_val

        st.markdown(
            f"### 💳 الصافي المطلوب: `{grand_total * exchange_rate:.2f}`"
        )

        col_b1, col_b2 = st.columns(2)
        with col_b1:
          checkout_btn = st.button(
              "✅ إتمام البيع وتوليد PDF",
              type="primary",
              use_container_width=True,
          )
        with col_b2:
          selected_cust_row = df_cust[df_cust["name"] == cust_name]
          phone_num = (
              selected_cust_row["phone"].values[0]
              if not selected_cust_row.empty
              else "962700000000"
          )
          wa_text = f"مرحباً {cust_name}، شكراً لتسوقك معنا. إجمالي فاتورتك: {grand_total:.2f} دينار."
          whatsapp_url = f"https://wa.me/{phone_num}?text={urllib.parse.quote(wa_text)}"
          st.markdown(
              f'<a href="{whatsapp_url}" target="_blank"><button style="background-color: #25d366; color: white; border: none; padding: 10px; border-radius: 8px; width: 100%; font-weight: bold; cursor: pointer;">💬 إرسال واتساب</button></a>',
              unsafe_allow_html=True,
          )

        if checkout_btn:
          conn = sqlite3.connect(DB_NAME)
          c = conn.cursor()
          now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          seller = st.session_state.get("logged_user", "admin")

          for item in st.session_state["cart"]:
            item_profit = item["profit"] - (
                disc_val / len(st.session_state["cart"])
            )
            c.execute(
                """
                            INSERT INTO sales (date, customer_name, product_name, quantity, total_price, discount, net_profit, seller_username, payment_type)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                (
                    now_str,
                    cust_name,
                    item["name"],
                    item["quantity"],
                    item["subtotal"],
                    disc_val,
                    item_profit,
                    seller,
                    pay_type,
                ),
            )
            c.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (item["quantity"], item["id"]),
            )

          if "آجل" in pay_type:
            c.execute(
                "UPDATE customers SET debt = debt + ?, total_spent ="
                " total_spent + ? WHERE name = ?",
                (grand_total, grand_total, cust_name),
            )
          else:
            c.execute(
                "UPDATE customers SET total_spent = total_spent + ?, points ="
                " points + ? WHERE name = ?",
                (grand_total, int(grand_total), cust_name),
            )

          conn.commit()
          c.execute("SELECT last_insert_rowid()")
          last_inv_id = c.fetchone()[0]
          conn.close()

          log_action(
              seller,
              "عملية بيع",
              f"فاتورة #{last_inv_id} بقيمة {grand_total:.2f} ({pay_type})",
          )

          pdf_bytes = generate_pdf_invoice(
              last_inv_id,
              cust_name,
              st.session_state["cart"],
              subtotal_val,
              disc_val,
              grand_total,
          )

          st.success("🎉 تمت عملية البيع بنجاح وتحديث النظام!")
          st.download_button(
              label="📥 تحميل الفاتورة الرسمية (PDF)",
              data=pdf_bytes,
              file_name=f"Invoice_{last_inv_id}.pdf",
              mime="application/pdf",
              type="primary",
          )
          st.session_state["cart"] = []

# ----------------------------------------------------
# 2. لوحة المؤشرات الذكية
# ----------------------------------------------------
elif menu == "📊 لوحة المؤشرات الذكية":
  st.header("📊 لوحة مؤشرات الأداء والتحليلات")

  conn = sqlite3.connect(DB_NAME)
  df_sales = pd.read_sql_query("SELECT * FROM sales", conn)
  df_exp = pd.read_sql_query("SELECT * FROM expenses", conn)
  conn.close()

  if df_sales.empty:
    st.info("💡 لا توجد مبيعات كافية لعرض الرسوم البيانية.")
  else:
    df_sales["date"] = pd.to_datetime(df_sales["date"])
    df_sales["hour"] = df_sales["date"].dt.hour
    df_sales["day_name"] = df_sales["date"].dt.day_name()

    tot_rev = df_sales["total_price"].sum()
    tot_prof = df_sales["net_profit"].sum()
    tot_exp = df_exp["amount"].sum() if not df_exp.empty else 0.0
    net_net = tot_prof - tot_exp

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("إجمالي المبيعات", f"{tot_rev:.2f} د.أ")
    m2.metric("إجمالي أرباح المنتجات", f"{tot_prof:.2f} د.أ")
    m3.metric("إجمالي المصروفات", f"{tot_exp:.2f} د.أ")
    m4.metric("صافي الربح النهائي", f"{net_net:.2f} د.أ")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
      st.subheader("⏰ المبيعات حسب ساعات اليوم")
      h_df = df_sales.groupby("hour")["total_price"].sum().reset_index()
      fig1 = px.bar(
          h_df,
          x="hour",
          y="total_price",
          labels={"hour": "الساعة", "total_price": "المبيعات"},
          color_discrete_sequence=["#d97706"],
      )
      st.plotly_chart(fig1, use_container_width=True)

    with c2:
      st.subheader("📅 المبيعات حسب أيام الأسبوع")
      d_df = df_sales.groupby("day_name")["total_price"].sum().reset_index()
      fig2 = px.pie(
          d_df,
          names="day_name",
          values="total_price",
          hole=0.4,
          color_discrete_sequence=px.colors.sequential.Sunset,
      )
      st.plotly_chart(fig2, use_container_width=True)

# ----------------------------------------------------
# 3. التنبؤ الذكي بالمبيعات (AI)
# ----------------------------------------------------
elif menu == "🤖 التنبؤ الذكي بالمبيعات (AI)":
  st.header("🤖 التنبؤ بحجم المبيعات المستقبلي (ميزة ذكاء اصطناعي)")
  conn = sqlite3.connect(DB_NAME)
  df_s = pd.read_sql_query("SELECT date, total_price FROM sales", conn)
  conn.close()

  if len(df_s) < 3:
    st.warning("⚠️ يلزم تسجيل 3 عمليات مبيعات على الأقل لتفعيل نموذج التنبؤ.")
  else:
    df_s["date"] = pd.to_datetime(df_s["date"])
    daily_sales = (
        df_s.groupby(df_s["date"].dt.date)["total_price"].sum().reset_index()
    )
    daily_sales["day_index"] = np.arange(len(daily_sales))

    X = daily_sales[["day_index"]]
    y = daily_sales["total_price"]

    from sklearn.linear_model import LinearRegression

    model = LinearRegression()
    model.fit(X, y)

    next_day_idx = np.array([[len(daily_sales)]])
    predicted_sales = model.predict(next_day_idx)[0]

    st.success(
        f"📈 بناءً على خوارزميات التعلم الآلي والبيانات السابقة، المبيعات المتوقعة"
        f" لليوم القادم تقريباً: **{max(0, predicted_sales):.2f} دينار**"
    )

    fig_ai = px.scatter(
        daily_sales,
        x="date",
        y="total_price",
        trendline="ols",
        labels={"date": "التاريخ", "total_price": "المبيعات اليومية"},
        title="تحليل واتجاه نمو المبيعات التاريخي",
    )
    st.plotly_chart(fig_ai, use_container_width=True)

# ----------------------------------------------------
# 4. إدارة الديون والذمم المالية
# ----------------------------------------------------
elif menu == "📖 إدارة الديون والذمم المالية":
  st.header("📖 سجل الديون والذمم المستحقة على العملاء")
  conn = sqlite3.connect(DB_NAME)
  df_debts = pd.read_sql_query(
      "SELECT id, name, phone, debt FROM customers WHERE debt > 0", conn
  )
  conn.close()

  if df_debts.empty:
    st.success("✅ لا توجد أي ديون مستحقة على العملاء حالياً!")
  else:
    st.dataframe(df_debts, use_container_width=True, hide_index=True)
    st.subheader("💳 سداد دفعة من الدين")

    with st.form("pay_debt_form"):
      c_sel = st.selectbox("اختر العميل:", df_debts["name"].tolist())
      p_amt = st.number_input("المبلغ المسدد (د.أ):", min_value=0.1)
      if st.form_submit_button("💰 تأكيد سداد الدين", type="primary"):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            "UPDATE customers SET debt = debt - ? WHERE name = ?",
            (p_amt, c_sel),
        )
        conn.commit()
        conn.close()
        st.success("تم تحديث حساب العميل وتسجيل السداد بنجاح!")
        st.rerun()

# ----------------------------------------------------
# 5. تنبيهات نقص المخزون
# ----------------------------------------------------
elif menu == "🚨 تنبيهات نقص المخزون":
  st.header("🚨 مراقبة النقص وإعادة التزويد")
  conn = sqlite3.connect(DB_NAME)
  df_low = pd.read_sql_query(
      "SELECT id, barcode, name, category, stock, min_stock FROM products"
      " WHERE stock <= min_stock",
      conn,
  )
  conn.close()

  if df_low.empty:
    st.success("✅ جميع الأصناف متوفرة بأرصدة آمنة تماماً!")
  else:
    st.error(f"⚠️ يوجد ({len(df_low)}) منتجات وصلت للحد الأدنى أو أقل!")
    st.dataframe(df_low, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# 6. إدارة العملاء وبرنامج الولاء (CRM)
# ----------------------------------------------------
elif menu == "👥 إدارة العملاء وبرنامج الولاء (CRM)":
  st.header("👥 مركز إدارة العملاء ونقاط الولاء")
  t1, t2 = st.tabs(["➕ إضافة عميل", "📋 قائمة العملاء"])

  with t1:
    with st.form("cust_f", clear_on_submit=True):
      cn = st.text_input("اسم العميل:")
      cp = st.text_input("رقم الهاتف (مثال: 9627xxxxxxxx):")
      ct = st.selectbox("التصنيف:", ["عادي", "برونزي", "فضي", "ذهبي (VIP)"])
      if st.form_submit_button("💾 حفظ العميل", type="primary"):
        if cn:
          try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute(
                "INSERT INTO customers (name, phone, tier) VALUES (?, ?, ?)",
                (cn, cp, ct),
            )
            conn.commit()
            conn.close()
            st.success("تم إضافة العميل بنجاح!")
            st.rerun()
          except sqlite3.IntegrityError:
            st.error("اسم العميل موجود مسبقاً!")

  with t2:
    conn = sqlite3.connect(DB_NAME)
    st.dataframe(
        pd.read_sql_query("SELECT * FROM customers", conn),
        use_container_width=True,
        hide_index=True,
    )
    conn.close()

# ----------------------------------------------------
# 7. إدارة المنتجات وتوليد الباركود
# ----------------------------------------------------
elif menu == "📦 إدارة المنتجات وتوليد الباركود":
  st.header("📦 إدارة المخزون وتوليد الباركود الحقيقي")
  t1, t2 = st.tabs(["➕ إضافة منتج جديد", "🏷️ عرض وطباعة الباركود"])

  with t1:
    with st.form("prod_f", clear_on_submit=True):
      c1, c2, c3 = st.columns(3)
      with c1:
        p_code = st.text_input("رمز الباركود (رقمي/إنجليزي):")
        p_name = st.text_input("اسم المنتج:")
      with c2:
        p_cat = st.text_input("التصنيف:", value="عام")
        p_price = st.number_input("سعر البيع (د.أ):", min_value=0.01)
      with c3:
        p_cost = st.number_input("سعر التكلفة (د.أ):", min_value=0.0)
        p_stock = st.number_input("الكمية الأولية:", min_value=1, value=10)

      if st.form_submit_button("💾 حفظ المنتج وتوليد الباركود", type="primary"):
        if p_code and p_name:
          try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute(
                "INSERT INTO products (barcode, name, category, price,"
                " cost_price, stock) VALUES (?, ?, ?, ?, ?, ?)",
                (p_code, p_name, p_cat, p_price, p_cost, p_stock),
            )
            conn.commit()
            conn.close()
            st.success("تم حفظ المنتج بنجاح!")
            st.rerun()
          except sqlite3.IntegrityError:
            st.error("الباركود مستخدم مسبقاً لصنف آخر!")

  with t2:
    df_prods = get_products()
    if not df_prods.empty:
      sel_p = st.selectbox(
          "اختر المنتج لعرض الباركود الحقيقي:", df_prods["name"].tolist()
      )
      p_row = df_prods[df_prods["name"] == sel_p].iloc[0]
      st.write(
          f"**المنتج:** {p_row['name']} | **الباركود:** `{p_row['barcode']}`"
      )
      try:
        b_img = create_barcode_image(str(p_row["barcode"]))
        st.image(b_img, caption=f"Barcode: {p_row['barcode']}")
        st.download_button(
            "📥 تحميل صورة الباركود",
            data=b_img,
            file_name=f"Barcode_{p_row['barcode']}.png",
            mime="image/png",
        )
      except Exception as e:
        st.error(f"خطأ في توليد الباركود: {e}")

# ----------------------------------------------------
# 8. المصروفات والنثريات المالية
# ----------------------------------------------------
elif menu == "💸 المصروفات والنثريات المالية":
  st.header("💸 المصروفات اليومية والنثريات")
  t1, t2 = st.tabs(["➕ تسجيل مصروف", "📋 سجل المصروفات"])

  with t1:
    with st.form("exp_f", clear_on_submit=True):
      e_title = st.text_input("عنوان المصروف (إيجار، كهرباء، رواتب...):")
      e_amt = st.number_input("المبلغ (د.أ):", min_value=0.1)
      e_cat = st.selectbox(
          "التصنيف:", ["تشغيلي", "رواتب", "فواتير وطاقة", "تسويق", "أخرى"]
      )
      e_notes = st.text_area("ملاحظات:")
      if st.form_submit_button("💾 حفظ المصروف", type="primary"):
        if e_title and e_amt > 0:
          conn = sqlite3.connect(DB_NAME)
          c = conn.cursor()
          c.execute(
              "INSERT INTO expenses (date, title, amount, category, notes)"
              " VALUES (?, ?, ?, ?, ?)",
              (
                  datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  e_title,
                  e_amt,
                  e_cat,
                  e_notes,
              ),
          )
          conn.commit()
          conn.close()
          st.success("تم تسجيل المصروف بنجاح!")
          st.rerun()

  with t2:
    conn = sqlite3.connect(DB_NAME)
    df_exps = pd.read_sql_query("SELECT * FROM expenses ORDER BY id DESC", conn)
    conn.close()
    if df_exps.empty:
      st.info("لا توجد مصروفات مسجلة.")
    else:
      st.dataframe(df_exps, use_container_width=True, hide_index=True)
      st.metric("إجمالي المصروفات", f"{df_exps['amount'].sum():.2f} د.أ")

# ----------------------------------------------------
# 9. طلبات الموردين والشراء
# ----------------------------------------------------
elif menu == "🚚 طلبات الموردين والشراء":
  st.header("🚚 سجل طلبات التوريد والشراء")
  t1, t2 = st.tabs(["➕ توريد بضاعة جديدة", "📋 سجل المشتريات"])
  df_p = get_products()

  with t1:
    if df_p.empty:
      st.warning("أضف منتجات للمخزن أولاً.")
    else:
      with st.form("pur_f", clear_on_submit=True):
        sup = st.text_input("اسم المورد / الشركة:")
        p_sel = st.selectbox("المنتج المراد توريده:", df_p["name"].tolist())
        q_add = st.number_input("الكمية المضافة:", min_value=1, value=10)
        c_tot = st.number_input("إجمالي التكلفة المدفوعة:", min_value=0.0)

        if st.form_submit_button("📥 تأكيد التوريد وتحديث المخزن", type="primary"):
          if sup:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute(
                "INSERT INTO purchases (date, supplier_name, product_name,"
                " quantity, total_cost) VALUES (?, ?, ?, ?, ?)",
                (
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    sup,
                    p_sel,
                    q_add,
                    c_tot,
                ),
            )
            c.execute(
                "UPDATE products SET stock = stock + ? WHERE name = ?",
                (q_add, p_sel),
            )
            conn.commit()
            conn.close()
            st.success("تم توريد البضاعة وتحديث المخزن بنجاح!")
            st.rerun()

  with t2:
    conn = sqlite3.connect(DB_NAME)
    df_purs = pd.read_sql_query("SELECT * FROM purchases ORDER BY id DESC", conn)
    conn.close()
    if df_purs.empty:
      st.info("لا توجد سجلات توريد سابقة.")
    else:
      st.dataframe(df_purs, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# 10. أرباح المنتجات والتقارير
# ----------------------------------------------------
elif menu == "📈 أرباح المنتجات والتقارير":
  st.header("📈 تقرير أداء وأرباح المنتجات")
  conn = sqlite3.connect(DB_NAME)
  df_rep = pd.read_sql_query(
      "SELECT product_name, SUM(quantity) as total_qty, SUM(total_price) as"
      " total_rev, SUM(net_profit) as total_prof FROM sales GROUP BY"
      " product_name",
      conn,
  )
  conn.close()

  if df_rep.empty:
    st.info("لا توجد بيانات مبيعات كافية لعرض تقرير الأرباح.")
  else:
    st.dataframe(df_rep, use_container_width=True, hide_index=True)
    st.subheader("📊 رسم بياني للأرباح حسب المنتجات")
    fig_p = px.bar(
        df_rep,
        x="product_name",
        y="total_prof",
        labels={"product_name": "المنتج", "total_prof": "صافي الربح (د.أ)"},
        color="total_prof",
        color_continuous_scale="Sunset",
    )
    st.plotly_chart(fig_p, use_container_width=True)

# ----------------------------------------------------
# 11. إدارة المستخدمين والصلاحيات
# ----------------------------------------------------
elif menu == "⚙️ إدارة المستخدمين والصلاحيات":
  st.header("⚙️ إدارة صلاحيات وحسابات النظام")
  t1, t2 = st.tabs(["➕ إضافة مستخدم", "📋 قائمة المستخدمين"])

  with t1:
    with st.form("new_u", clear_on_submit=True):
      nu = st.text_input("اسم المستخدم الجديد:")
      np = st.text_input("كلمة المرور:", type="password")
      nr = st.selectbox("الصلاحية:", ["مدير النظام", "موظف مبيعات"])
      if st.form_submit_button("💾 إنشاء الحساب", type="primary"):
        if nu and np:
          try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (nu, np, nr),
            )
            conn.commit()
            conn.close()
            st.success(f"تم إنشاء حساب `{nu}` بنجاح!")
            st.rerun()
          except sqlite3.IntegrityError:
            st.error("اسم المستخدم مستخدم مسبقاً!")

  with t2:
    conn = sqlite3.connect(DB_NAME)
    df_u = pd.read_sql_query("SELECT id, username, role FROM users", conn)
    conn.close()
    st.dataframe(df_u, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# 12. سجل الرقابة الأمنية (Audit Log)
# ----------------------------------------------------
elif menu == "📜 سجل الرقابة الأمنية (Audit Log)":
  st.header("📜 سجل العمليات والرقابة الأمنية")
  conn = sqlite3.connect(DB_NAME)
  st.dataframe(
      pd.read_sql_query("SELECT * FROM audit_logs ORDER BY id DESC", conn),
      use_container_width=True,
      hide_index=True,
  )
  conn.close()

# ----------------------------------------------------
# 13. النسخ الاحتياطي
# ----------------------------------------------------
elif menu == "💾 النسخ الاحتياطي":
  st.header("💾 النسخ الاحتياطي لقاعدة البيانات")
  with open(DB_NAME, "rb") as f:
    st.download_button(
        "💾 تحميل نسخة قاعدة البيانات الاحتياطية `.db`",
        data=f,
        file_name=f"Backup_{datetime.date.today()}.db",
        mime="application/x-sqlite3",
        type="primary",
        use_container_width=True,
    )
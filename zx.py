import streamlit as st
import sqlite3
import pandas as pd
import datetime
import os

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
# 2. إنشاء وتحديث قاعدة البيانات (لا تمسح البيانات القديمة أبداً)
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
    
    # التحقق من وجود مستخدمين افتراضيين فقط إذا كان الجدول فارغاً تماماً
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", "admin123", "Admin"))
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("cashier1", "1234", "Cashier"))
        
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

# ----------------------------------------------------
# 3. إدارة جلسة تسجيل الدخول (Authentication State)
# ----------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "logged_user" not in st.session_state:
    st.session_state["logged_user"] = None
if "user_role" not in st.session_state:
    st.session_state["user_role"] = None
if "cart" not in st.session_state:
    st.session_state["cart"] = []

# ----------------------------------------------------
# 4. شاشة تسجيل الدخول المخصصة مع الترحيب 🔒
# ----------------------------------------------------
if not st.session_state["authenticated"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown("""
        <div class="welcome-card">
            <h1 style="color: #f59e0b; margin-bottom: 5px;">👑 متجر الهاشمية</h1>
            <h3 style="color: #f8fafc; font-size: 18px; margin-top: 0;">أهلاً وسهلاً بكم في نظام المبيعات والمخزون الذكي</h3>
            <p style="color: #9ca3af; font-size: 13px;">يرجى إدخال بيانات حسابك لتسجيل الدخول لبدء العمليات</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")

        with st.form("login_form", clear_on_submit=False):
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
                    log_action(username_input, "تسجيل دخول", "تم تسجيل الدخول بنجاح للنظام")
                    st.success(f"مرحباً بك مجدداً {username_input}!")
                    st.rerun()
                else:
                    st.error("❌ خطأ: اسم المستخدم أو كلمة السر غير صحيحة!")

    st.stop()

# ----------------------------------------------------
# 5. القائمة الجانبية وزر خروج الفعلي 🚪
# ----------------------------------------------------
st.sidebar.title("👑 متجر الهاشمية")
st.sidebar.markdown(f"👤 **المستخدم:** `{st.session_state['logged_user']}`")
st.sidebar.markdown(f"🛡️ **الصلاحية:** `{st.session_state['user_role']}`")

if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
    log_action(st.session_state["logged_user"], "تسجيل خروج", "تم تسجيل الخروج من النظام")
    st.session_state["authenticated"] = False
    st.session_state["logged_user"] = None
    st.session_state["user_role"] = None
    st.session_state["cart"] = []
    st.rerun()

st.sidebar.write("---")

current_role = st.session_state.get("user_role", "Cashier")

if current_role == "Admin":
    menu_options = [
        "🛒 كاشير المبيعات (POS)",
        "🚨 تنبيهات النقص وإعادة التزويد",
        "📙 سجل الذمم وتسديد الديون",
        "🔄 إرجاع واستبدال الفواتير",
        "📦 إدارة وتعديل المخزون",
        "🏷️ طباعة بطاقات الأسعار",
        "📊 التقارير المالية والأرباح",
        "📜 سجل الأحداث والرقابة (Audit Log)",
        "⚙️ النسخ الاحتياطي للنظام",
        "👥 إدارة الحسابات والصلاحيات"
    ]
elif current_role == "Inventory":
    menu_options = [
        "📦 إدارة وتعديل المخزون",
        "🚨 تنبيهات النقص وإعادة التزويد",
        "🏷️ طباعة بطاقات الأسعار",
        "👥 إدارة الحسابات والصلاحيات"
    ]
else:
    menu_options = [
        "🛒 كاشير المبيعات (POS)",
        "🔄 إرجاع واستبدال الفواتير",
        "📙 سجل الذمم وتسديد الديون",
        "👥 إدارة الحسابات والصلاحيات"
    ]

menu = st.sidebar.radio("القائمة الرئيسية 🔱", menu_options)

def get_products():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()
    return df

# ----------------------------------------------------
# 1. كاشير المبيعات
# ----------------------------------------------------
if menu == "🛒 كاشير المبيعات (POS)":
    st.header("🛒 نقطة البيع السريعة - متجر الهاشمية")
    df_products = get_products()

    if df_products.empty:
        st.warning("⚠️ لا توجد منتجات بالمخزن. يرجى إضافة منتجات من شاشة المخزون أولاً.")
    else:
        col_scan, col_cart = st.columns([1.3, 1.1])

        with col_scan:
            st.subheader("📦 كافة المنتجات المتاحة")
            search_query = st.text_input("🔎 تصفية سريعة (اسم / باركود):", key="pos_search")
            
            filtered_df = df_products
            if search_query:
                filtered_df = df_products[
                    df_products["name"].str.contains(search_query, case=False, na=False) |
                    df_products["barcode"].str.contains(search_query, case=False, na=False)
                ]

            if not filtered_df.empty:
                for idx, prod in filtered_df.iterrows():
                    with st.container():
                        p_col1, p_col2, p_col3, p_col4 = st.columns([2.5, 1.2, 1.2, 1])
                        
                        p_col1.write(f"**{prod['name']}**\n*(كود: {prod['barcode']})*")
                        p_col2.write(f"السعر: **{prod['price']:.2f} د.أ**")
                        p_col3.write(f"المخزون: `{prod['stock']}`")
                        
                        if p_col4.button("➕ إضافة", key=f"add_btn_{prod['id']}"):
                            if prod['stock'] <= 0:
                                st.error("المادة غير متوفرة بالمخزن!")
                            else:
                                existing_item = next((item for item in st.session_state["cart"] if item["id"] == prod['id']), None)
                                if existing_item:
                                    if existing_item['quantity'] + 1 > prod['stock']:
                                        st.error("الكمية المطلوبة تتجاوز المخزون!")
                                    else:
                                        existing_item['quantity'] += 1
                                        existing_item['subtotal'] = existing_item['quantity'] * existing_item['price']
                                        existing_item['profit'] = (existing_item['price'] - existing_item['cost_price']) * existing_item['quantity']
                                        st.rerun()
                                else:
                                    st.session_state["cart"].append({
                                        "id": prod['id'],
                                        "name": prod['name'],
                                        "price": prod['price'],
                                        "cost_price": prod['cost_price'],
                                        "quantity": 1,
                                        "subtotal": prod['price'],
                                        "profit": prod['price'] - prod['cost_price']
                                    })
                                    st.rerun()
                        st.markdown("<hr style='margin: 4px 0; border-color: #374151;'>", unsafe_allow_html=True)
            else:
                st.warning("لا توجد مواد تطابق البحث.")

        with col_cart:
            st.subheader("🛒 محتويات الفاتورة الحالية")
            if not st.session_state["cart"]:
                st.info("السلة فارغة. اضغط (➕ إضافة) بجانب أي منتج من القائمة.")
            else:
                for idx, item in enumerate(st.session_state["cart"]):
                    c_name, c_qty, c_price, c_del = st.columns([2, 1.5, 1.2, 0.6])
                    c_name.write(f"**{item['name']}**")
                    
                    prod_in_db = df_products[df_products["id"] == item["id"]].iloc[0]
                    new_q = c_qty.number_input("الكمية", min_value=1, max_value=int(prod_in_db["stock"]), value=int(item["quantity"]), key=f"q_input_{idx}", label_visibility="collapsed")
                    
                    if new_q != item["quantity"]:
                        item["quantity"] = new_q
                        item["subtotal"] = new_q * item["price"]
                        item["profit"] = (item["price"] - item["cost_price"]) * new_q
                        st.rerun()

                    c_price.write(f"**{item['subtotal']:.2f} د.أ**")
                    
                    if c_del.button("❌", key=f"del_{idx}"):
                        st.session_state["cart"].pop(idx)
                        st.rerun()

                st.write("---")
                subtotal_val = sum(item['subtotal'] for item in st.session_state["cart"])
                
                st.markdown("#### 🏷️ نظام الخصم المتعدد")
                disc_type = st.radio("نوع الخصم:", ["مبلغ ثابت (د.أ)", "نسبة مئوية (%)"], horizontal=True)
                
                col_d1, col_d2 = st.columns(2)
                if disc_type == "مبلغ ثابت (د.أ)":
                    discount_val = col_d1.number_input("قيمة الخصم (د.أ):", min_value=0.0, max_value=float(subtotal_val), value=0.0, step=0.5)
                else:
                    disc_perc = col_d1.number_input("نسبة الخصم (%):", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
                    discount_val = (disc_perc / 100.0) * subtotal_val

                grand_total = subtotal_val - discount_val
                col_d2.markdown(f"### 💳 الصافي: `{grand_total:.2f} د.أ`")
                
                cust_name = st.text_input("اسم الزبون:", value="زبون عام")
                pay_method = st.radio("طريقة الدفع:", ["نقداً (Cash)", "بطاقة (Card)", "ذمم / دين"], horizontal=True)

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✅ إتمام عملية البيع", type="primary", use_container_width=True):
                        conn = sqlite3.connect(DB_NAME)
                        c = conn.cursor()
                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        seller = st.session_state.get("logged_user", "admin")
                        
                        for item in st.session_state["cart"]:
                            item_net_profit = item['profit'] - (discount_val / len(st.session_state["cart"]))
                            c.execute("""
                                INSERT INTO sales (date, customer_name, product_name, quantity, total_price, discount, net_profit, payment_method, seller_username)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (now_str, cust_name, item['name'], item['quantity'], item['subtotal'], discount_val, item_net_profit, pay_method, seller))
                            
                            c.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item['quantity'], item['id']))
                        
                        if pay_method == "ذمم / دين":
                            c.execute("INSERT INTO debts (customer_name, amount, date, notes, status) VALUES (?, ?, ?, ?, ?)", 
                                      (cust_name, grand_total, now_str, f"فاتورة شراء من متجر الهاشمية بتاريخ {now_str}", "غير مدفوع"))
                        
                        conn.commit()
                        conn.close()
                        
                        log_action(seller, "عملية بيع", f"فاتورة بقيمة {grand_total:.2f} د.أ - الزبون: {cust_name}")
                        st.session_state["cart"] = []
                        st.success("🎉 تم إتمام العملية بنجاح!")
                        st.rerun()

                with col_btn2:
                    if st.button("🗑️ تفريغ السلة", use_container_width=True):
                        st.session_state["cart"] = []
                        st.rerun()

# ----------------------------------------------------
# 2. تنبيهات النقص وإعادة التزويد
# ----------------------------------------------------
elif menu == "🚨 تنبيهات النقص وإعادة التزويد":
    st.header("🚨 مراقبة النقص وإعادة الشحن")
    conn = sqlite3.connect(DB_NAME)
    df_low = pd.read_sql_query("SELECT id, barcode, name, category, stock, min_stock FROM products WHERE stock <= min_stock", conn)
    conn.close()

    if df_low.empty:
        st.balloons()
        st.success("✅ جميع الأصناف والمواد متوفرة بأسعار ورصيد آمن بالمخزن!")
    else:
        st.error(f"⚠️ يوجد ({len(df_low)}) منتجات وصلت أو قلت عن حد الأمان!")
        st.dataframe(df_low[["barcode", "name", "category", "stock", "min_stock"]], use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("⚡ تزويد سريع للمخزون")
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            restock_prod_id = st.selectbox("اختر الصنف لتزويده:", df_low["id"].tolist(), format_func=lambda x: df_low[df_low["id"]==x]["name"].values[0])
        with col_r2:
            add_qty = st.number_input("الكمية المضافة:", min_value=1, value=10)
        with col_r3:
            st.write(" ")
            st.write(" ")
            if st.button("📥 تحديث المخزون فوراً", type="primary"):
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (add_qty, restock_prod_id))
                conn.commit()
                conn.close()
                log_action(st.session_state["logged_user"], "إعادة شحن مخزون", f"إضافة كمية ({add_qty}) للمادة رقم #{restock_prod_id}")
                st.success("تم تحديث الرصيد بنجاح!")
                st.rerun()

# ----------------------------------------------------
# 3. سجل الذمم وتسديد الديون
# ----------------------------------------------------
elif menu == "📙 سجل الذمم وتسديد الديون":
    st.header("📙 سجل متابعة وتسديد الديون والذمم")
    conn = sqlite3.connect(DB_NAME)
    df_debts = pd.read_sql_query("SELECT * FROM debts", conn)
    conn.close()

    if df_debts.empty:
        st.info("💡 لا توجد ديون أو ذمم تسديد مسجلة حالياً.")
    else:
        st.dataframe(df_debts, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("💵 تسديد دين زبون")
        
        unpaid_debts = df_debts[df_debts["status"] != "تم التسديد"]
        if unpaid_debts.empty:
            st.success("✅ جميع الذمم والديون مسددة بالكامل!")
        else:
            d_id = st.selectbox("اختر الدين المطلوب تسديده:", unpaid_debts["id"].tolist(), 
                                format_func=lambda x: f"رقم #{x} - {unpaid_debts[unpaid_debts['id']==x]['customer_name'].values[0]} ({unpaid_debts[unpaid_debts['id']==x]['amount'].values[0]} د.أ)")
            
            curr_debt = unpaid_debts[unpaid_debts["id"] == d_id].iloc[0]
            pay_amount = st.number_input("المبلغ المدفوع (د.أ):", min_value=0.1, max_value=float(curr_debt["amount"]), value=float(curr_debt["amount"]))
            
            if st.button("💳 تحصيل الدفعة والتسديد", type="primary"):
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                rem_amount = curr_debt["amount"] - pay_amount
                
                if rem_amount <= 0:
                    c.execute("UPDATE debts SET amount = 0, status = 'تم التسديد' WHERE id = ?", (d_id,))
                else:
                    c.execute("UPDATE debts SET amount = ? WHERE id = ?", (rem_amount, d_id))
                
                conn.commit()
                conn.close()
                log_action(st.session_state["logged_user"], "تسديد دين", f"تسديد دفعة بقيمة {pay_amount} د.أ من دين #{d_id} للزبون {curr_debt['customer_name']}")
                st.success("تم تسجيل التسديد بنجاح!")
                st.rerun()

# ----------------------------------------------------
# 4. قسم إرجاع واستبدال الفواتير 🔄
# ----------------------------------------------------
elif menu == "🔄 إرجاع واستبدال الفواتير":
    st.header("🔄 قسم استرجاع واستبدال الفواتير المطور")
    
    conn = sqlite3.connect(DB_NAME)
    df_sales = pd.read_sql_query("SELECT * FROM sales ORDER BY id DESC", conn)
    conn.close()

    if df_sales.empty:
        st.info("💡 لا توجد عمليات مبيعات مسجلة لإرجاعها.")
    else:
        st.subheader("🔎 البحث في الفواتير")
        search_invoice = st.text_input("ادخل رقم الفاتورة / اسم الزبون / اسم المنتج:", placeholder="ابحث هنا...")
        
        filtered_sales = df_sales
        if search_invoice:
            filtered_sales = df_sales[
                df_sales['id'].astype(str).str.contains(search_invoice, case=False, na=False) |
                df_sales['customer_name'].str.contains(search_invoice, case=False, na=False) |
                df_sales['product_name'].str.contains(search_invoice, case=False, na=False)
            ]

        st.dataframe(filtered_sales, use_container_width=True, hide_index=True)
        st.divider()

        st.subheader("🛠️ تنفيذ عملية الإرجاع")
        
        if filtered_sales.empty:
            st.warning("لا توجد فواتير تطابق عملية البحث.")
        else:
            selected_sale_id = st.selectbox(
                "اختر العملية المراد إرجاعها:", 
                filtered_sales["id"].tolist(),
                format_func=lambda x: f"فاتورة #{x} | الزبون: {df_sales[df_sales['id']==x]['customer_name'].values[0]} | المادة: {df_sales[df_sales['id']==x]['product_name'].values[0]} | الكمية المباعة: {df_sales[df_sales['id']==x]['quantity'].values[0]}"
            )

            sale_row = df_sales[df_sales["id"] == selected_sale_id].iloc[0]
            
            with st.container():
                st.markdown(f"""
                <div class="gold-box">
                    <strong>تفاصيل العملية المختارة:</strong><br>
                    • رقم الفاتورة: #{sale_row['id']} | التاريخ: {sale_row['date']}<br>
                    • الزبون: {sale_row['customer_name']} | طريقة الدفع: {sale_row['payment_method']}<br>
                    • المنتج: {sale_row['product_name']} | السعر الإجمالي: {sale_row['total_price']:.2f} د.أ
                </div>
                """, unsafe_allow_html=True)

                col_rf1, col_rf2 = st.columns(2)
                with col_rf1:
                    return_qty = st.number_input("حدد الكمية المراد إرجاعها:", min_value=1, max_value=int(sale_row['quantity']), value=int(sale_row['quantity']))
                
                unit_price = sale_row['total_price'] / sale_row['quantity']
                refund_amount = return_qty * unit_price
                
                with col_rf2:
                    st.markdown(f"### 💵 المبلغ المسترجع: `{refund_amount:.2f} د.أ`")

                if st.button("🔄 تأكيد عملية الإرجاع وصرف المستحقات", type="primary", use_container_width=True):
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    
                    c.execute("UPDATE products SET stock = stock + ? WHERE name = ?", (return_qty, sale_row['product_name']))
                    
                    if return_qty == sale_row['quantity']:
                        c.execute("DELETE FROM sales WHERE id = ?", (selected_sale_id,))
                    else:
                        new_qty = sale_row['quantity'] - return_qty
                        new_total = new_qty * unit_price
                        new_profit = sale_row['net_profit'] * (new_qty / sale_row['quantity'])
                        c.execute("UPDATE sales SET quantity = ?, total_price = ?, net_profit = ? WHERE id = ?", 
                                  (new_qty, new_total, new_profit, selected_sale_id))

                    if sale_row['payment_method'] == "ذمم / دين":
                        c.execute("SELECT id, amount FROM debts WHERE customer_name = ? AND status = 'غير مدفوع' ORDER BY id DESC LIMIT 1", (sale_row['customer_name'],))
                        debt_record = c.fetchone()
                        if debt_record:
                            d_id, curr_amt = debt_record
                            new_amt = max(0.0, curr_amt - refund_amount)
                            if new_amt == 0:
                                c.execute("UPDATE debts SET amount = 0, status = 'تم التسديد' WHERE id = ?", (d_id,))
                            else:
                                c.execute("UPDATE debts SET amount = ? WHERE id = ?", (new_amt, d_id))

                    conn.commit()
                    conn.close()

                    log_action(st.session_state["logged_user"], "إرجاع فاتورة", f"إرجاع {return_qty} من {sale_row['product_name']} بقيمة {refund_amount:.2f} د.أ للزبون {sale_row['customer_name']}")

                    st.success(f"🎉 تم إرجاع {return_qty} قطعة بنجاح وتحديث الرصيد بالمخزن!")

                    receipt_html = f"""
                    <div style="border:2px dashed #f59e0b; padding:15px; border-radius:10px; text-align:center; color:white; background-color:#111827; width:300px; margin:auto;">
                        <h3 style="color:#f59e0b; margin:0;">👑 متجر الهاشمية</h3>
                        <p style="margin:5px 0;"><strong>سند إرجاع مبيعات</strong></p>
                        <hr style="border-color:#374151;">
                        <p style="text-align:right; font-size:12px;">
                        رقم الإرجاع: #{selected_sale_id}<br>
                        التاريخ: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}<br>
                        الزبون: {sale_row['customer_name']}<br>
                        المادة: {sale_row['product_name']}<br>
                        الكمية المرتجعة: {return_qty}<br>
                        المبلغ المردود: {refund_amount:.2f} د.أ
                        </p>
                        <hr style="border-color:#374151;">
                        <p style="font-size:11px; color:#9ca3af;">شكراً لتعاملكم مع متجر الهاشمية</p>
                    </div>
                    """
                    st.markdown(receipt_html, unsafe_allow_html=True)
                    st.download_button("🖨️ طباعة سند الإرجاع (HTML)", data=f"<html><body onload='window.print();'>{receipt_html}</body></html>", file_name=f"Return_{selected_sale_id}.html", mime="text/html")

# ----------------------------------------------------
# 5. إدارة وتعديل المخزون
# ----------------------------------------------------
elif menu == "📦 إدارة وتعديل المخزون":
    st.header("📦 إدارة المنتجات وتحديث المخزون")
    
    tab1, tab2 = st.tabs(["➕ إضافة صنف جديد", "🛠️ تعديل أو حذف صنف"])
    
    with tab1:
        with st.form("add_prod_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                p_code = st.text_input("رمز الباركود:")
                p_name = st.text_input("اسم المنتج:")
            with c2:
                p_cat = st.text_input("التصنيف:", value="عام")
                p_price = st.number_input("سعر البيع (د.أ):", min_value=0.01, step=0.1)
            with c3:
                p_cost = st.number_input("سعر التكلفة (د.أ):", min_value=0.0, step=0.1)
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
                        log_action(st.session_state["logged_user"], "إضافة صنف", f"إضافة {p_name} (باركود: {p_code})")
                        st.success("تم إضافة الصنف للمخزن بنجاح!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("الباركود مستخدم لمنتج آخر!")

    with tab2:
        df_prods = get_products()
        if not df_prods.empty:
            edit_p_id = st.selectbox("اختر الصنف للتعديل عليه:", df_prods["id"].tolist(),
                                     format_func=lambda x: f"{df_prods[df_prods['id']==x]['name'].values[0]} - [{df_prods[df_prods['id']==x]['barcode'].values[0]}]")
            
            p_selected = df_prods[df_prods["id"] == edit_p_id].iloc[0]
            
            with st.form("edit_prod_form"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_name = st.text_input("اسم المنتج:", value=p_selected["name"])
                    e_price = st.number_input("سعر البيع:", value=float(p_selected["price"]))
                    e_stock = st.number_input("الكمية بالمخزن:", value=int(p_selected["stock"]))
                with ec2:
                    e_cat = st.text_input("التصنيف:", value=p_selected["category"])
                    e_cost = st.number_input("سعر التكلفة:", value=float(p_selected["cost_price"]))
                    e_min = st.number_input("حد النقص الأدنى:", value=int(p_selected["min_stock"]))

                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    if st.form_submit_button("💾 تحديث البيانات", type="primary"):
                        conn = sqlite3.connect(DB_NAME)
                        c = conn.cursor()
                        c.execute("""
                            UPDATE products SET name=?, category=?, price=?, cost_price=?, stock=?, min_stock=?
                            WHERE id=?
                        """, (e_name, e_cat, e_price, e_cost, e_stock, e_min, edit_p_id))
                        conn.commit()
                        conn.close()
                        log_action(st.session_state["logged_user"], "تعديل صنف", f"تعديل المنتج #{edit_p_id} ({e_name})")
                        st.success("تم التعديل بنجاح!")
                        st.rerun()

            if st.button(f"🗑️ حذف ({p_selected['name']}) نهائياً", type="secondary"):
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("DELETE FROM products WHERE id = ?", (edit_p_id,))
                conn.commit()
                conn.close()
                log_action(st.session_state["logged_user"], "حذف صنف", f"حذف الصنف #{edit_p_id}")
                st.success("تم الحذف بنجاح!")
                st.rerun()

    st.subheader("📋 كشف المواد المسجلة")
    st.dataframe(get_products(), use_container_width=True, hide_index=True)

# ----------------------------------------------------
# 6. طباعة بطاقات الأسعار المصممة
# ----------------------------------------------------
elif menu == "🏷️ طباعة بطاقات الأسعار":
    st.header("🏷️ تصميم وطباعة بطاقات الأسعار لمتجر الهاشمية")
    df_products = get_products()
    
    if df_products.empty:
        st.info("💡 لا توجد منتجات لتصميم بطاقات أسعار لها.")
    else:
        col_opt1, col_opt2, col_opt3 = st.columns(3)
        with col_opt1:
            selected_tag_prod = st.selectbox("🎯 اختر المنتج:", df_products["name"].tolist())
            prod_data = df_products[df_products["name"] == selected_tag_prod].iloc[0]
        with col_opt2:
            tag_style = st.selectbox("🎨 النمط والقالب:", [
                "🥇 قالب الهاشمية الذهبي الفاخر",
                "💥 قالب العروض والتخفيضات",
                "🌿 القالب العصري البسيط"
            ])
        with col_opt3:
            tag_size = st.radio("📐 الحجم:", ["صغير للرفوف", "كبير للملصقات"], horizontal=True)

        card_width = "380px" if "كبير" in tag_size else "280px"
        font_size_price = "42px" if "كبير" in tag_size else "32px"

        p_name = prod_data['name']
        p_cat = prod_data['category']
        p_price = f"{prod_data['price']:.2f}"
        p_code = prod_data['barcode']
        p_id = prod_data['id']

        if "الذهبي" in tag_style:
            tag_html = f"""
            <div style="border: 2px solid #d97706; background: #111827; padding: 16px; border-radius: 14px; width: {card_width}; text-align: center; margin: auto; font-family: sans-serif; color: white;">
                <div style="border-bottom: 1px solid #374151; padding-bottom: 6px; margin-bottom: 10px;">
                    <span style="color: #f59e0b; font-weight: bold; font-size: 15px;">👑 متجر الهاشمية</span>
                </div>
                <h3 style="color: #ffffff; margin: 6px 0; font-size: 20px;">{p_name}</h3>
                <p style="color: #9ca3af; font-size: 12px; margin: 0 0 10px 0;">التصنيف: {p_cat}</p>
                <div style="background: rgba(245, 158, 11, 0.15); border: 1px dashed #f59e0b; padding: 8px; border-radius: 10px; margin: 10px 0;">
                    <span style="color: #10b981; font-size: {font_size_price}; font-weight: bold;">{p_price}</span>
                    <span style="color: #10b981; font-size: 16px; font-weight: bold;"> د.أ</span>
                </div>
                <div style="font-size: 11px; color: #9ca3af; margin-top: 8px;">
                    رمز الباركود: {p_code}
                </div>
            </div>
            """
        elif "العروض" in tag_style:
            tag_html = f"""
            <div style="border: 3px solid #ef4444; background: #ffffff; padding: 16px; border-radius: 14px; width: {card_width}; text-align: center; margin: auto; font-family: sans-serif; color: #111827;">
                <div style="background-color: #ef4444; color: white; font-weight: bold; font-size: 13px; padding: 4px 0; border-radius: 6px; margin-bottom: 8px;">
                    🔥 عرض خاص - الهاشمية 🔥
                </div>
                <h3 style="color: #111827; margin: 6px 0; font-size: 20px;">{p_name}</h3>
                <div style="background-color: #fef2f2; border: 2px solid #fca5a5; padding: 8px; border-radius: 10px; margin: 8px 0;">
                    <span style="color: #dc2626; font-size: {font_size_price}; font-weight: bold;">{p_price}</span>
                    <span style="color: #dc2626; font-size: 16px; font-weight: bold;"> د.أ</span>
                </div>
                <div style="font-size: 11px; color: #9ca3af; margin-top: 6px;">
                    كود: {p_code}
                </div>
            </div>
            """
        else:
            tag_html = f"""
            <div style="border: 1px solid #d1d5db; background: #f9fafb; padding: 16px; border-radius: 12px; width: {card_width}; text-align: center; margin: auto; font-family: sans-serif; color: #111827;">
                <h4 style="color: #4b5563; margin: 0 0 4px 0; font-size: 13px;">👑 متجر الهاشمية</h4>
                <h3 style="color: #1f2937; margin: 6px 0; font-size: 19px;">{p_name}</h3>
                <h2 style="color: #059669; font-size: {font_size_price}; margin: 8px 0; font-weight: bold;">
                    {p_price} <span style="font-size:15px;">د.أ</span>
                </h2>
                <div style="font-size: 11px; color: #6b7280;">
                    الباركود: {p_code}
                </div>
            </div>
            """

        st.markdown(tag_html, unsafe_allow_html=True)
        
        print_code = f"<html><body onload='window.print(); window.close();'>{tag_html}</body></html>"
        st.download_button(
            label="🖨️ طباعة بطاقة السعر (HTML)",
            data=print_code,
            file_name=f"PriceTag_{p_id}.html",
            mime="text/html",
            type="primary",
            use_container_width=True
        )

# ----------------------------------------------------
# 7. التقارير المالية والأرباح المحدثة 📊
# ----------------------------------------------------
elif menu == "📊 التقارير المالية والأرباح":
    st.header("📊 لوحة المبيعات والتحليلات المالية المتقدمة")
    
    conn = sqlite3.connect(DB_NAME)
    df_sales = pd.read_sql_query("SELECT * FROM sales", conn)
    conn.close()

    if df_sales.empty:
        st.info("لا توجد مبيعات مسجلة للتقرير حالياً.")
    else:
        df_sales["total_price"] = pd.to_numeric(df_sales["total_price"], errors="coerce").fillna(0.0)
        df_sales["discount"] = pd.to_numeric(df_sales["discount"], errors="coerce").fillna(0.0)
        df_sales["net_profit"] = pd.to_numeric(df_sales["net_profit"], errors="coerce").fillna(0.0)
        df_sales["quantity"] = pd.to_numeric(df_sales["quantity"], errors="coerce").fillna(0)

        df_sales["date_only"] = pd.to_datetime(df_sales["date"]).dt.date

        st.markdown("#### 📅 فلترة التقارير حسب النطاق الزمني")
        filter_option = st.selectbox("اختر الفترة:", ["الكل", "اليوم الحالي", "آخر 7 أيام", "آخر 30 يوماً", "تاريخ مخصص"])

        today_date = datetime.date.today()
        filtered_df = df_sales

        if filter_option == "اليوم الحالي":
            filtered_df = df_sales[df_sales["date_only"] == today_date]
        elif filter_option == "آخر 7 أيام":
            start_date = today_date - datetime.timedelta(days=7)
            filtered_df = df_sales[df_sales["date_only"] >= start_date]
        elif filter_option == "آخر 30 يوماً":
            start_date = today_date - datetime.timedelta(days=30)
            filtered_df = df_sales[df_sales["date_only"] >= start_date]
        elif filter_option == "تاريخ مخصص":
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                from_d = st.date_input("من تاريخ:", value=today_date - datetime.timedelta(days=7))
            with col_d2:
                to_d = st.date_input("إلى تاريخ:", value=today_date)
            filtered_df = df_sales[(df_sales["date_only"] >= from_d) & (df_sales["date_only"] <= to_d)]

        if filtered_df.empty:
            st.warning("⚠️ لا توجد مبيعات مسجلة ضمن النطاق الزمني المحدد.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("إجمالي المبيعات", f"{filtered_df['total_price'].sum():.2f} د.أ")
            m2.metric("إجمالي الخصومات", f"{filtered_df['discount'].sum():.2f} د.أ")
            m3.metric("صافي الأرباح", f"{filtered_df['net_profit'].sum():.2f} د.أ")
            m4.metric("عدد الفواتير/العمليات", len(filtered_df))

            st.divider()

            col_ch1, col_ch2 = st.columns(2)
            
            with col_ch1:
                st.subheader("💳 المبيعات حسب طريقة الدفع")
                payment_summary = filtered_df.groupby("payment_method")["total_price"].sum().reset_index()
                payment_summary.columns = ["طريقة الدفع", "إجمالي المبلغ (د.أ)"]
                st.dataframe(payment_summary, use_container_width=True, hide_index=True)

            with col_ch2:
                st.subheader("🏆 أفضل المنتجات مبيعاً")
                top_products = filtered_df.groupby("product_name").agg(
                    quantity=("quantity", "sum"),
                    total_price=("total_price", "sum")
                ).reset_index()
                top_products.columns = ["اسم المنتج", "الكمية المباعة", "إجمالي المبيعات (د.أ)"]
                top_products = top_products.sort_values(by="الكمية المباعة", ascending=False)
                st.dataframe(top_products, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("📈 رسم بياني لحركة المبيعات اليومية")
            daily_chart_data = filtered_df.groupby("date_only")["total_price"].sum().reset_index()
            daily_chart_data.columns = ["التاريخ", "المبيعات"]
            daily_chart_data = daily_chart_data.set_index("التاريخ")
            st.line_chart(daily_chart_data)

            st.divider()
            st.subheader("📋 سجل العمليات التفصيلي للفترة")
            st.dataframe(filtered_df.drop(columns=["date_only"]), use_container_width=True, hide_index=True)

            csv_data = filtered_df.drop(columns=["date_only"]).to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 تصدير التقرير المالي المصفى إلى CSV/Excel",
                data=csv_data,
                file_name=f"Report_AlHashemiah_{datetime.date.today()}.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True
            )

# ----------------------------------------------------
# 8. سجل الأحداث والرقابة (Audit Log)
# ----------------------------------------------------
elif menu == "📜 سجل الأحداث والرقابة (Audit Log)":
    st.header("📜 سجل الرقابة والمتابعة الأمنية (Audit Log)")
    conn = sqlite3.connect(DB_NAME)
    df_logs = pd.read_sql_query("SELECT * FROM audit_logs ORDER BY id DESC", conn)
    conn.close()

    if df_logs.empty:
        st.info("سجل الرقابة فارغ.")
    else:
        st.dataframe(df_logs, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# 9. النسخ الاحتياطي للنظام
# ----------------------------------------------------
elif menu == "⚙️ النسخ الاحتياطي للنظام":
    st.header("⚙️ النسخ الاحتياطي لقاعدة البيانات")
    try:
        with open(DB_NAME, "rb") as db_file:
            st.download_button(
                "💾 تنزيل نسخة احتياطية من القاعدة (al_hashemiah_pos.db)",
                data=db_file,
                file_name=f"AlHashemiah_backup_{datetime.date.today()}.db",
                mime="application/x-sqlite3",
                type="primary",
                use_container_width=True
            )
    except Exception as e:
        st.error(f"خطأ: {e}")

# ----------------------------------------------------
# 10. إدارة الحسابات والصلاحيات
# ----------------------------------------------------
elif menu == "👥 إدارة الحسابات والصلاحيات":
    st.header("👥 مركز التحكم والمستخدمين والصلاحيات")
    
    curr_user = st.session_state.get("logged_user", "admin")
    curr_role = st.session_state.get("user_role", "Admin")

    tab_my, tab_new, tab_all = st.tabs(["🔐 حسابي الشخصي", "➕ إضافة مستخدم جديد", "🛠️ إدارة الحسابات"])

    with tab_my:
        st.subheader("🔑 تعديل الحساب الحالي")
        with st.form("my_acc_form"):
            new_u = st.text_input("اسم المستخدم الحالي:", value=curr_user)
            new_p = st.text_input("كلمة السر الجديدة:", type="password")
            confirm_p = st.text_input("تأكيد كلمة السر:", type="password")
            
            if st.form_submit_button("💾 حفظ البيانات", type="primary"):
                if new_p and new_p != confirm_p:
                    st.error("كلمتا السر غير متطابقتين!")
                else:
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    if new_p:
                        c.execute("UPDATE users SET username=?, password=? WHERE username=?", (new_u, new_p, curr_user))
                    else:
                        c.execute("UPDATE users SET username=? WHERE username=?", (new_u, curr_user))
                    conn.commit()
                    conn.close()
                    st.session_state["logged_user"] = new_u
                    st.success("تم التحديث بنجاح!")
                    st.rerun()

    with tab_new:
        if curr_role != "Admin":
            st.warning("هذه الصلاحية مقتصرة على المسؤول (Admin).")
        else:
            with st.form("add_u_form", clear_on_submit=True):
                au = st.text_input("اسم المستخدم الجديد:")
                ap = st.text_input("كلمة السر:", type="password")
                ar = st.selectbox("مستوى الصلاحية:", ["Cashier", "Inventory", "Admin"])
                
                if st.form_submit_button("➕ إنشاء الحساب", type="primary"):
                    if au and ap:
                        try:
                            conn = sqlite3.connect(DB_NAME)
                            c = conn.cursor()
                            c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (au, ap, ar))
                            conn.commit()
                            conn.close()
                            log_action(curr_user, "إضافة مستخدم", f"إضافة حساب {au} بصلاحية [{ar}]")
                            st.success("تم إنشاء حساب الموظف بنجاح!")
                        except sqlite3.IntegrityError:
                            st.error("اسم المستخدم مسجل مسبقاً!")

    with tab_all:
        if curr_role != "Admin":
            st.warning("هذه الصلاحية مقتصرة على المسؤول (Admin).")
        else:
            conn = sqlite3.connect(DB_NAME)
            df_users = pd.read_sql_query("SELECT id, username, role FROM users", conn)
            conn.close()
            st.dataframe(df_users, use_container_width=True, hide_index=True)
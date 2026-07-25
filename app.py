import streamlit as st
import random
import google.generativeai as genai

# إعدادات الصفحة
st.set_page_config(page_title="مكتبة الهاشمية", page_icon="📚", layout="wide")

# 1. تهيئة البيانات في الـ Session State
if "books_db" not in st.session_state:
    st.session_state.books_db = {
        "🤖 الذكاء الاصطناعي والتكنولوجيا": [
            {"title": "الذكاء الاصطناعي: مقدمة قصيرة جداً", "author": "مارغريت بودن", "link": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"},
            {"title": "Superintelligence", "author": "Nick Bostrom", "link": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"},
            {"title": "Clean Code", "author": "Robert C. Martin", "link": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"},
            {"title": "Python Crash Course", "author": "Eric Matthes", "link": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"}
        ],
        "📖 كتب عربية متنوعة": [
            {"title": "ثلاثية غرناطة", "author": "رضوى عاشور", "link": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"},
            {"title": "مهزلة العقل البشري", "author": "علي الوردي", "link": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"},
            {"title": "الفيل الأزرق", "author": "أحمد مراد", "link": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"}
        ],
        "🌍 كتب أجنبية متنوعة": [
            {"title": "Atomic Habits", "author": "James Clear", "link": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"},
            {"title": "1984", "author": "George Orwell", "link": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"},
            {"title": "The Psychology of Money", "author": "Morgan Housel", "link": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"}
        ]
    }

if "reading_book" not in st.session_state:
    st.session_state.reading_book = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

completion_notes = [
    "🌟 **إنجاز جديد يُضاف لرصيدك المعرفي!**\n\n> *'العقل لا يعود أبداً إلى أبعاده الأولى بعد أن يتسع لفكرة جديدة.'*",
    "💡 **معرفة جديدة تُضاف لمهاراتك!**\n\n> *'التكنولوجيا والفكر يُبنيان بالمعرفة، وأنت اليوم أضفت لَبنة جديدة لبنائك.'*",
    "🎭 **رحلة فكرية مكتملة!**\n\n> *'القارئ يعيش ألف حياة قبل أن يموت.'* جاهز للرحلة القادمة؟ 📖✨",
    "🚀 **أحسنت!**\n\n> قراءة هذا الكتاب هي خطوة جديدة في رحلة تطورك. لا تنسَ تدوين أهم الفوائد لتترسخ في ذهنك."
]

# العنوان الرئيسي
st.title("📚 مكتبة الهاشمية التفاعلية")
st.markdown("---")

# القائمة الجانبية للتنقل
menu = st.sidebar.radio("القائمة الرئيسية", ["عرض المكتبة", "🤖 مساعد الهاشمية الذكي", "➕ إضافة كتاب جديد"])

# ---------------- 1. عرض المكتبة وقراءة الكتاب ----------------
if menu == "عرض المكتبة":
    
    # إذا كان المستخدم يقرأ كتاباً حالياً
    if st.session_state.reading_book:
        book = st.session_state.reading_book
        st.button("⬅️ العودة للمكتبة", on_click=lambda: st.session_state.update({"reading_book": None}))
        st.subheader(f"📖 أنت تقرأ الآن: {book['title']} - {book['author']}")
        
        # عرض الكتاب في إطار (PDF Viewer / Embed)
        st.components.v1.iframe(book["link"], height=600, scrolling=True)
        
        st.markdown("---")
        if st.button("أنهيت قراءة الكتاب ✅", type="primary"):
            st.balloons()
            st.success(f"مبروك! أنهيت قراءة **{book['title']}**")
            st.info(random.choice(completion_notes))
            st.session_state.reading_book = None

    else:
        st.subheader("📚 الأقسام والكتب المتاحة")
        category = st.selectbox("اختر القسم:", list(st.session_state.books_db.keys()))
        
        st.write(f"### كتب قسم: {category}")
        books = st.session_state.books_db[category]
        
        for idx, book in enumerate(books):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"📖 **{book['title']}** - *{book['author']}*")
            with col2:
                if st.button("اقرأ الآن 👁️", key=f"read_{category}_{idx}"):
                    st.session_state.reading_book = book
                    st.rerun()
            with col3:
                if st.button("أنهيت القراءة ✅", key=f"done_{category}_{idx}"):
                    st.balloons()
                    st.success(f"تم تسجيل قراءة: **{book['title']}**")
                    st.info(random.choice(completion_notes))

# ---------------- 2. مساعد الذكاء الاصطناعي الكامل ----------------
elif menu == "🤖 مساعد الهاشمية الذكي":
    st.subheader("🤖 مساعد الهاشمية الذكي (Gemini AI)")
    
    # إدخال الـ API Key في الشريط الجانبي لضمان الأمان والتشغيل
    api_key = st.sidebar.text_input("مفتاح API Key لـ Gemini:", type="password", help="أدخل مفتاح Google AI Studio الخاص بك هنا")
    st.write("اسأل الذكاء الاصطناعي عن أي كتاب، تلخيص، أو اقتراحات قراءة!")

    if not api_key:
        st.info("💡 لتفعيل الذكاء الاصطناعي بشكل كامل، يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية اليسرى.")
    else:
        genai.configure(api_key=api_key)
        
        # عرض سجل المحادثة
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
        # إدخال سؤال من المستخدم
        if user_input := st.chat_input("اكتب سؤالك هنا (مثلاً: تلخيص كتاب 1984، أو ترشيح كتاب ذكاء اصطناعي)..."):
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
                
            with st.chat_message("assistant"):
                with st.spinner("جاري التفكير بالرد..."):
                    try:
                        # استدعاء نموذج Gemini الرسمي
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        prompt = f"أنت مساعد ذكي ومثقف في 'مكتبة الهاشمية'. أجب عن هذا السؤال بدقة ولطف: {user_input}"
                        response = model.generate_content(prompt)
                        
                        ai_response = response.text
                        st.markdown(ai_response)
                        st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء الاتصال بالذكاء الاصطناعي: {e}")

# ---------------- 3. إضافة كتاب جديد ----------------
elif menu == "➕ إضافة كتاب جديد":
    st.subheader("➕ إضافة كتاب جديد إلى مكتبة الهاشمية")
    
    selected_cat = st.selectbox("اختر القسم لإضافة الكتاب:", list(st.session_state.books_db.keys()))
    title = st.text_input("اسم الكتاب:")
    author = st.text_input("اسم المؤلف:")
    pdf_link = st.text_input("رابط ملف الكتاب (PDF):", value="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf")
    
    if st.button("حفظ الكتاب 💾"):
        if title.strip() and author.strip():
            st.session_state.books_db[selected_cat].append({
                "title": title.strip(),
                "author": author.strip(),
                "link": pdf_link.strip()
            })
            st.success(f"✅ تم إضافة '{title}' بنجاح إلى قسم {selected_cat}!")
        else:
            st.warning("⚠️ يرجى ملء اسم الكتاب والمؤلف.")

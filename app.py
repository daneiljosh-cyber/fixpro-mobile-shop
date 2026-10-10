import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import urllib.parse

# #########################################################
# DATABASE INITIALIZATION
# #########################################################
def get_db_connection():
    conn = sqlite3.connect("mobile_shop.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Repair Tickets Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            device_model TEXT NOT NULL,
            imei TEXT,
            issue_description TEXT NOT NULL,
            estimated_cost REAL NOT NULL,
            advance_paid REAL DEFAULT 0.0,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Sales Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            sale_price REAL NOT NULL,
            cost_price REAL DEFAULT 0.0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# #########################################################
# APP LAYOUT & CONFIG
# #########################################################
st.set_page_config(page_title="FixPro - Mobile Repair Hub", page_icon="📱", layout="wide")

st.title("📱 FixPro — Mobile Repair & Shop Management")

# Sidebar Navigation
menu = st.sidebar.radio(
    "Navigation", 
    ["📊 Dashboard & Insights", "🔧 Repair Job Sheets", "🛒 Sales & Quick POS", "📜 History & Logs"]
)

conn = get_db_connection()

# #########################################################
# 1. DASHBOARD & INSIGHTS
# #########################################################
if menu == "📊 Dashboard & Insights":
    st.header("📊 Business Insights")
    
    # Query Data for Metrics
    today = datetime.now().strftime("%Y-%m-%d")
    
    today_sales_df = pd.read_sql_query(
        f"SELECT SUM(sale_price) as total FROM sales WHERE DATE(timestamp) = '{today}'", conn
    )
    daily_revenue = today_sales_df['total'].iloc[0] or 0.0

    tickets_df = pd.read_sql_query("SELECT * FROM tickets", conn)
    
    pending_count = len(tickets_df[tickets_df['status'].isin(['PENDING', 'IN_PROGRESS'])])
    ready_count = len(tickets_df[tickets_df['status'] == 'READY'])
    
    # Calculate unpaid balances on active jobs
    active_jobs = tickets_df[tickets_df['status'] != 'DELIVERED']
    pending_dues = (active_jobs['estimated_cost'] - active_jobs['advance_paid']).sum() if not active_jobs.empty else 0.0

    # Key Metrics Display
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Today's Direct Revenue", f"₹{daily_revenue:,.2f}")
    col2.metric("Pending Repairs", pending_count)
    col3.metric("Ready for Pickup", ready_count)
    col4.metric("Pending Customer Dues", f"₹{pending_dues:,.2f}")

    st.markdown("---")

    # Quick Visuals
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Repair Status Breakdown")
        if not tickets_df.empty:
            status_counts = tickets_df['status'].value_counts()
            st.bar_chart(status_counts)
        else:
            st.info("No repair tickets registered yet.")

    with c2:
        st.subheader("Recent Sales Activity")
        recent_sales = pd.read_sql_query("SELECT item_name, category, sale_price, timestamp FROM sales ORDER BY id DESC LIMIT 5", conn)
        if not recent_sales.empty:
            st.dataframe(recent_sales, use_container_width=True)
        else:
            st.info("No sales recorded today.")

# #########################################################
# 2. REPAIR JOB SHEETS
# #########################################################
elif menu == "🔧 Repair Job Sheets":
    st.header("🔧 Repair Job Management")
    
    tab1, tab2 = st.tabs(["📋 Active Job Tickets", "➕ New Job Ticket"])

    # TAB 1: Active Tickets
    with tab1:
        active_df = pd.read_sql_query("SELECT * FROM tickets WHERE status != 'DELIVERED' ORDER BY id DESC", conn)
        
        if active_df.empty:
            st.info("No active repairs in progress.")
        else:
            for idx, row in active_df.iterrows():
                with st.expander(f"📌 Ticket #{row['id']} — {row['device_model']} ({row['customer_name']}) — Status: {row['status']}"):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    
                    with c1:
                        st.write(f"**Customer:** {row['customer_name']} ({row['customer_phone']})")
                        st.write(f"**IMEI / Serial:** {row['imei'] or 'N/A'}")
                        st.write(f"**Issue:** {row['issue_description']}")
                    
                    with c2:
                        balance = row['estimated_cost'] - row['advance_paid']
                        st.write(f"**Est. Cost:** ₹{row['estimated_cost']}")
                        st.write(f"**Advance Paid:** ₹{row['advance_paid']}")
                        st.write(f"**Due Amount:** ₹{balance}")
                    
                    with c3:
                        # Status Update
                        status_list = ["PENDING", "IN_PROGRESS", "READY", "DELIVERED", "CANCELLED"]
                        current_index = status_list.index(row['status']) if row['status'] in status_list else 0
                        
                        new_status = st.selectbox(
                            "Update Status", 
                            status_list, 
                            index=current_index,
                            key=f"status_{row['id']}"
                        )
                        
                        if st.button("Save Status", key=f"btn_{row['id']}"):
                            cursor = conn.cursor()
                            cursor.execute("UPDATE tickets SET status = ? WHERE id = ?", (new_status, row['id']))
                            conn.commit()
                            st.success("Status Updated!")
                            st.rerun()

                        # WhatsApp Quick Message Generator
                        msg = f"Hello {row['customer_name']}, your device ({row['device_model']}) repair status is updated to: *{row['status']}*. Remaining due: ₹{balance}."
                        encoded_msg = urllib.parse.quote(msg)
                        wa_url = f"https://api.whatsapp.com/send?phone={row['customer_phone']}&text={encoded_msg}"
                        st.markdown(f"[💬 Notify on WhatsApp]({wa_url})")

    # TAB 2: Create Ticket
    with tab2:
        st.subheader("Register New Repair Ticket")
        with st.form("new_ticket_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                cust_name = st.text_input("Customer Name *")
                cust_phone = st.text_input("Customer Phone Number *")
                device_model = st.text_input("Device Model (e.g. iPhone 13, Redmi Note 10) *")
                imei = st.text_input("IMEI / Serial Number (Optional)")
            
            with col2:
                issue = st.text_area("Reported Issue / Fault Description *")
                cost = st.number_input("Estimated Total Cost (₹)", min_value=0.0, step=50.0)
                advance = st.number_input("Advance Paid (₹)", min_value=0.0, step=50.0)
            
            submit = st.form_submit_button("Create Job Ticket")
            
            if submit:
                if not cust_name or not cust_phone or not device_model or not issue:
                    st.error("Please fill in all required fields marked with *")
                else:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO tickets (customer_name, customer_phone, device_model, imei, issue_description, estimated_cost, advance_paid) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (cust_name, cust_phone, device_model, imei, issue, cost, advance)
                    )
                    conn.commit()
                    st.success("Repair Job Sheet Created Successfully!")
                    st.rerun()

# #########################################################
# 3. SALES & QUICK POS
# #########################################################
elif menu == "🛒 Sales & Quick POS":
    st.header("🛒 Quick Point of Sale")

    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Record New Sale")
        with st.form("quick_sale_form", clear_on_submit=True):
            item_name = st.text_input("Item / Service Name (e.g. Temper Glass, Charger, Screen Replacement)")
            category = st.selectbox("Category", ["Accessory", "Spare Part", "Repair Service", "Other"])
            price = st.number_input("Sale Amount (₹)", min_value=0.0, step=10.0)
            cost_price = st.number_input("Cost Amount / Expense (₹) [Optional]", min_value=0.0, step=10.0)
            
            sale_submitted = st.form_submit_button("Record Sale")
            if sale_submitted:
                if item_name and price > 0:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO sales (item_name, category, sale_price, cost_price) VALUES (?, ?, ?, ?)",
                        (item_name, category, price, cost_price)
                    )
                    conn.commit()
                    st.success(f"Sale recorded: {item_name} for ₹{price}")
                    st.rerun()
                else:
                    st.error("Please enter a valid item name and price.")

    with col2:
        st.subheader("Today's Transactions")
        sales_df = pd.read_sql_query("SELECT id, item_name, category, sale_price, timestamp FROM sales WHERE DATE(timestamp) = DATE('now') ORDER BY id DESC", conn)
        if not sales_df.empty:
            st.dataframe(sales_df, use_container_width=True)
        else:
            st.info("No sales logged for today yet.")

# #########################################################
# 4. HISTORY & LOGS
# #########################################################
elif menu == "📜 History & Logs":
    st.header("📜 Store Logs & All Records")
    
    tab1, tab2 = st.tabs(["All Repair Tickets", "All Sales Records"])
    
    with tab1:
        all_tickets = pd.read_sql_query("SELECT * FROM tickets ORDER BY id DESC", conn)
        st.dataframe(all_tickets, use_container_width=True)
        
    with tab2:
        all_sales = pd.read_sql_query("SELECT * FROM sales ORDER BY id DESC", conn)
        st.dataframe(all_sales, use_container_width=True)

conn.close()

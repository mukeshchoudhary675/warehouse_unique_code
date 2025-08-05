import streamlit as st
import pandas as pd
from rapidfuzz import process, fuzz
from io import BytesIO

st.set_page_config(page_title="Warehouse Deduplicator", layout="wide")

st.title("📦 Warehouse Deduplicator")
st.markdown("Upload your Excel file with warehouse data to clean up duplicate codes.")

uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    st.subheader("Step 1: Select Columns")
    warehouse_code_col = st.selectbox("Select Warehouse Code column", df.columns)
    warehouse_name_col = st.selectbox("Select Warehouse Name column", df.columns)
    address_cols = st.multiselect("Select address/location columns to use for matching", df.columns)

    if st.button("Run Deduplication"):
        with st.spinner("Processing and matching..."):
            df["merged_address"] = df[warehouse_name_col] + " " + df[address_cols].astype(str).agg(" ".join, axis=1)

            unique_list = []
            code_map = {}
            new_codes = {}
            code_counter = 1

            for idx, row in df.iterrows():
                current_str = row["merged_address"]

                match_found = False
                for unique in unique_list:
                    if fuzz.token_sort_ratio(current_str, unique) > 90:
                        group_key = unique
                        match_found = True
                        break

                if not match_found:
                    group_key = current_str
                    unique_list.append(group_key)
                    new_codes[group_key] = f"WH-{code_counter:04d}"
                    code_counter += 1

                code_map[row[warehouse_code_col]] = new_codes[group_key]

            df["Cleaned Warehouse Code"] = df[warehouse_code_col].map(code_map)
            df["Warehouse Group"] = df["merged_address"].map(new_codes)

            # Display results
            st.success(f"✅ Found {len(unique_list)} unique warehouse groups.")
            st.dataframe(df[[warehouse_code_col, "Cleaned Warehouse Code", warehouse_name_col] + address_cols].head(50))

            # Download
            output = BytesIO()
            df.drop(columns=["merged_address", "Warehouse Group"]).to_excel(output, index=False, engine="openpyxl")
            st.download_button("📥 Download Cleaned File", data=output.getvalue(), file_name="cleaned_warehouse_data.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

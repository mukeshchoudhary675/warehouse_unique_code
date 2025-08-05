import streamlit as st
import pandas as pd
from rapidfuzz import process, fuzz
from io import BytesIO

st.set_page_config(page_title="Warehouse Deduplicator", layout="wide")

st.title("📦 Warehouse Deduplicator with Verification")
st.markdown("Upload your Excel file and group warehouses by fuzzy matching logic.")

uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    st.subheader("Step 1: Select Columns")
    warehouse_code_col = st.selectbox("Select Warehouse Code column", df.columns)
    warehouse_name_col = st.selectbox("Select Warehouse Name column", df.columns)
    address_cols = st.multiselect("Select address/location columns for matching", df.columns)

    if st.button("Run Matching and Grouping"):
        with st.spinner("Processing..."):
            # Combine name and address
            df["combined_address"] = df[warehouse_name_col].fillna('') + " " + df[address_cols].astype(str).agg(" ".join, axis=1)

            unique_groups = []
            group_map = {}
            group_ids = {}
            group_counter = 1

            for idx, row in df.iterrows():
                text = row["combined_address"]

                matched = False
                for group in unique_groups:
                    if fuzz.token_sort_ratio(text, group) > 90:
                        matched_group = group
                        matched = True
                        break

                if not matched:
                    matched_group = text
                    unique_groups.append(text)

                group_map[idx] = matched_group

            # Assign group ID and new cleaned warehouse code
            for i, group in enumerate(unique_groups, start=1):
                group_ids[group] = f"WH-{i:04d}"

            df["Warehouse Group"] = df.index.map(lambda x: group_map[x])
            df["Cleaned Warehouse Code"] = df["Warehouse Group"].map(group_ids)

            # Count how many rows belong to each group
            group_counts = df["Warehouse Group"].value_counts().to_dict()
            df["Warehouse Match Count"] = df["Warehouse Group"].map(group_counts)

            # Summary section
            st.subheader("📊 Summary")
            st.markdown(f"🔢 Total rows in dataset: **{len(df)}**")
            st.markdown(f"📛 Unique warehouse names (raw): **{df[warehouse_name_col].nunique()}**")
            st.markdown(f"🧠 Unique fuzzy-matched warehouse groups: **{len(unique_groups)}**")
            st.markdown(f"📦 Cleaned codes assigned: **{df['Cleaned Warehouse Code'].nunique()}**")

            # Show sample results
            st.subheader("🔍 Sample of Matched Results")
            st.dataframe(df[[warehouse_code_col, "Cleaned Warehouse Code", warehouse_name_col, "Warehouse Match Count"] + address_cols].head(50))

            # Download cleaned result
            output = BytesIO()
            df.drop(columns=["combined_address", "Warehouse Group"]).to_excel(output, index=False, engine="openpyxl")
            st.download_button(
                label="📥 Download Cleaned File",
                data=output.getvalue(),
                file_name="cleaned_warehouse_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

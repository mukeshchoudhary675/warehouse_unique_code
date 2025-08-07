import streamlit as st
import pandas as pd
import re
from io import BytesIO
from rapidfuzz import fuzz

st.title("📦 Unique Warehouse Code Cleaner")

uploaded_file = st.file_uploader("Upload your warehouse Excel file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Let user pick column names
    warehouse_code_col = st.selectbox("Select Warehouse Code Column", df.columns)
    warehouse_name_col = st.selectbox("Select Warehouse Name Column", df.columns)
    address_col = st.selectbox("Select Address Column (Line 1 or Combined)", df.columns)

    if st.button("🚀 Generate Unique Warehouse Codes"):

        df = df.copy()

        # Clean and normalize text for comparison
        def normalize(text):
            if pd.isna(text):
                return ""
            text = str(text).lower()
            text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text

        df["Normalized Name"] = df[warehouse_name_col].apply(normalize)
        df["Normalized Address"] = df[address_col].apply(normalize)

        # Group by name first
        grouped = {}
        group_id = 1

        for idx, row in df.iterrows():
            name = row["Normalized Name"]
            address = row["Normalized Address"]

            matched = False
            for key in grouped:
                if key["name"] == name:
                    # Same name, now compare address
                    if key["address"] == address:
                        grouped[key]["rows"].append(idx)
                        matched = True
                        break
                    else:
                        # Check if address is significantly different (e.g., different chamber no.)
                        chamber_1 = re.findall(r"chamber\s*no\.?\s*\d+", key["address"])
                        chamber_2 = re.findall(r"chamber\s*no\.?\s*\d+", address)
                        if chamber_1 != chamber_2:
                            continue  # treat as different
                        # If chamber is same or not found, treat as same
                        grouped[key]["rows"].append(idx)
                        matched = True
                        break

            if not matched:
                grouped[{"name": name, "address": address}] = {"rows": [idx], "group_id": group_id}
                group_id += 1

        # Assign cleaned codes
        cleaned_codes = [None] * len(df)
        warehouse_match_count = [0] * len(df)
        split_flag = ["✅ SAME"] * len(df)

        for group in grouped.values():
            code = f"WH-{group['group_id']:04d}"
            count = len(group["rows"])
            for i in group["rows"]:
                cleaned_codes[i] = code
                warehouse_match_count[i] = count
            # If count > 1 but from same name → mark as SPLIT due to address
            if count > 1:
                name_check = df.loc[group["rows"], warehouse_name_col].nunique()
                if name_check == 1:
                    for i in group["rows"]:
                        split_flag[i] = "🔺 SPLIT"

        df["Cleaned Warehouse Code"] = cleaned_codes
        df["Warehouse Match Count"] = warehouse_match_count
        df["Split by Address?"] = split_flag

        # Raw count check
        raw_counts = df[warehouse_name_col].value_counts().to_dict()
        df["Raw Warehouse Match Count"] = df[warehouse_name_col].map(raw_counts)

        df["Match Check"] = df.apply(
            lambda row: "✅ MATCH" if row["Raw Warehouse Match Count"] == row["Warehouse Match Count"] else "❌ MISMATCH",
            axis=1
        )

        # Reorder columns
        final_cols = [
            warehouse_code_col,
            warehouse_name_col,
            address_col,
            "Cleaned Warehouse Code",
            "Warehouse Match Count",
            "Raw Warehouse Match Count",
            "Match Check",
            "Split by Address?"
        ]

        grouped_df = df[final_cols].copy()

        # Sheet 2: Unique only
        unique_cleaned = grouped_df.drop_duplicates(subset=["Cleaned Warehouse Code"])[
            ["Cleaned Warehouse Code", warehouse_name_col, address_col, "Split by Address?"]
        ].sort_values("Cleaned Warehouse Code")

        # Output download
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            grouped_df.to_excel(writer, index=False, sheet_name="Full Cleaned Output")
            unique_cleaned.to_excel(writer, index=False, sheet_name="Unique Warehouses Only")

        st.success("✅ Warehouse Codes Cleaned Successfully!")
        st.download_button(
            label="📥 Download Cleaned Excel",
            data=output.getvalue(),
            file_name="Cleaned_Warehouse_Codes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

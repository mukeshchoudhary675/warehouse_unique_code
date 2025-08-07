import streamlit as st
import pandas as pd
import io
from rapidfuzz import fuzz

st.title("🧹 Clean & Deduplicate Warehouse Codes")

uploaded_file = st.file_uploader("Upload your warehouse Excel file", type=[".xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()

    # Detect column names
    warehouse_code_col = next((col for col in df.columns if "code" in col.lower()), df.columns[0])
    warehouse_name_col = next((col for col in df.columns if "name" in col.lower()), df.columns[1])

    # Address column selection
    address_candidates = [col for col in df.columns if "address" in col.lower()]
    address_col = address_candidates[0] if address_candidates else df.columns[2]

    df[warehouse_code_col] = df[warehouse_code_col].astype(str).str.strip()
    df[warehouse_name_col] = df[warehouse_name_col].astype(str).str.strip()
    df[address_col] = df[address_col].astype(str).str.strip()

    # Create composite key (exact name match only)
    df["Warehouse Name Upper"] = df[warehouse_name_col].str.upper().str.strip()
    df["Address Cleaned"] = df[address_col].str.upper().str.strip()

    # Extract leading number info (chamber, godown etc.)
    import re
    def extract_leading_number(text):
        match = re.search(r'(CHAMBER|GODOWN|ROOM)[^\d]*(\d+[A-Z]?)', text)
        return match.group(2) if match else ''

    df["Address Keyword"] = df["Address Cleaned"].apply(extract_leading_number)

    # Group by exact warehouse name
    grouped = df.groupby("Warehouse Name Upper")

    cleaned_rows = []
    code_counter = 1
    for name, group in grouped:
        # Now within each warehouse name, group by address differences
        address_groups = []
        for _, row in group.iterrows():
            matched = False
            for g in address_groups:
                # Match by address fuzzy similarity but NOT if keyword is different
                sim = fuzz.token_set_ratio(row["Address Cleaned"], g[0]["Address Cleaned"])
                keyword_match = row["Address Keyword"] == g[0]["Address Keyword"]
                if sim >= 90 and keyword_match:
                    g.append(row)
                    matched = True
                    break
            if not matched:
                address_groups.append([row])

        # Assign unique cleaned warehouse code to each address group
        for group_rows in address_groups:
            for row in group_rows:
                row_dict = row.to_dict()
                row_dict["Cleaned Warehouse Code"] = f"WH-{code_counter:04d}"
                cleaned_rows.append(row_dict)
            code_counter += 1

    # Final DataFrame
    grouped_df = pd.DataFrame(cleaned_rows)

    # Add warehouse name match count (raw + cleaned)
    name_counts_raw = df["Warehouse Name Upper"].value_counts().to_dict()
    name_counts_cleaned = grouped_df["Warehouse Name Upper"].value_counts().to_dict()

    grouped_df["Raw Warehouse Match Count"] = grouped_df["Warehouse Name Upper"].map(name_counts_raw)
    grouped_df["Warehouse Match Count"] = grouped_df["Warehouse Name Upper"].map(name_counts_cleaned)

    grouped_df["Match Check"] = grouped_df["Raw Warehouse Match Count"] == grouped_df["Warehouse Match Count"]

    # Check if a warehouse name was split into multiple cleaned codes
    name_code_counts = grouped_df.groupby("Warehouse Name Upper")["Cleaned Warehouse Code"].nunique().to_dict()
    grouped_df["Split by Address?"] = grouped_df["Warehouse Name Upper"].map(
        lambda x: "❗ SPLIT" if name_code_counts.get(x, 1) > 1 else "✅ SAME"
    )

    # Final sheet 2: only 1 record per cleaned warehouse code
    unique_cleaned = grouped_df.drop_duplicates(subset=["Cleaned Warehouse Code"])[
        ["Cleaned Warehouse Code", warehouse_name_col, address_col, "Split by Address?"]
    ].sort_values("Cleaned Warehouse Code")

    # Downloadable output
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        grouped_df.to_excel(writer, index=False, sheet_name="Full Cleaned Output")
        unique_cleaned.to_excel(writer, index=False, sheet_name="Unique Warehouses Only")

    st.success("✅ Processing complete. Download your cleaned file below:")
    st.download_button("📥 Download Cleaned Excel", output.getvalue(), file_name="cleaned_warehouses.xlsx")



























# import streamlit as st
# import pandas as pd
# from rapidfuzz import fuzz
# import re
# from io import BytesIO

# st.set_page_config(page_title="Exact Name + Smart Address Matcher", layout="wide")
# st.title("📦 Smart Warehouse Code Assigner (Exact Name + Address Match)")
# st.markdown("This app uses **exact match on names** and **smart fuzzy address matching** that respects numeric differences like 'Chamber No. 1' vs 'Chamber No. 2'.")

# uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])

# def extract_numeric_keywords(text):
#     """Extracts chamber/godown/gala + numbers like 'Chamber No.1', 'Godown No.2'"""
#     matches = re.findall(r"(chamber|godown|gala)[^\d]{0,5}(\d{1,2}[a-zA-Z]{0,1})", text.lower())
#     return set([" ".join(match).strip() for match in matches])

# if uploaded_file:
#     df = pd.read_excel(uploaded_file)

#     st.subheader("Step 1: Select Columns")
#     warehouse_code_col = st.selectbox("Select Warehouse Code column", df.columns)
#     warehouse_name_col = st.selectbox("Select Warehouse Name column", df.columns)
#     address_col = st.selectbox("Select the full address column", df.columns)

#     if st.button("Assign Cleaned Codes"):
#         with st.spinner("Processing..."):

#             df["Cleaned Warehouse Code"] = None
#             df["Match Check"] = None

#             group_id = 1
#             grouped_df = pd.DataFrame()

#             for name, group in df.groupby(warehouse_name_col):
#                 group = group.copy()
#                 group["assigned"] = False
#                 codes = {}

#                 for i, row in group.iterrows():
#                     if group.at[i, "assigned"]:
#                         continue

#                     base_text = row[address_col]
#                     base_nums = extract_numeric_keywords(base_text)
#                     matched_indices = [i]
#                     group.at[i, "assigned"] = True

#                     for j, comp_row in group.iterrows():
#                         if i == j or group.at[j, "assigned"]:
#                             continue

#                         comp_text = comp_row[address_col]
#                         comp_nums = extract_numeric_keywords(comp_text)
#                         score = fuzz.token_sort_ratio(base_text, comp_text)

#                         # Check fuzzy match + numeric patterns
#                         if score > 90 and base_nums != comp_nums:
#                             continue  # treat as different if numbers differ

#                         if score > 90 and base_nums == comp_nums:
#                             matched_indices.append(j)
#                             group.at[j, "assigned"] = True

#                     cleaned_code = f"WH-{group_id:04d}"
#                     group.loc[group.index.isin(matched_indices), "Cleaned Warehouse Code"] = cleaned_code
#                     group.loc[group.index.isin(matched_indices), "Match Check"] = f"✅ Group {group_id}"
#                     group_id += 1

#                 grouped_df = pd.concat([grouped_df, group])

#             # Raw match count by name
#             raw_name_counts = df[warehouse_name_col].value_counts().to_dict()
#             grouped_df["Raw Warehouse Match Count"] = grouped_df[warehouse_name_col].map(raw_name_counts)

#             # Grouped match count by cleaned code
#             group_counts = grouped_df["Cleaned Warehouse Code"].value_counts().to_dict()
#             grouped_df["Warehouse Match Count"] = grouped_df["Cleaned Warehouse Code"].map(group_counts)

#             # Check if a warehouse name was split into multiple cleaned codes
#             name_code_counts = grouped_df.groupby(warehouse_name_col)["Cleaned Warehouse Code"].nunique().to_dict()
#             grouped_df["Split by Address?"] = grouped_df[warehouse_name_col].map(
#                 lambda x: "❗ SPLIT" if name_code_counts.get(x, 1) > 1 else "✅ SAME"
#             )


#             # Summary
#             st.subheader("📊 Summary")
#             st.markdown(f"🧾 Total rows: **{len(grouped_df)}**")
#             st.markdown(f"🏷️ Unique raw warehouse names: **{df[warehouse_name_col].nunique()}**")
#             st.markdown(f"📦 Cleaned unique warehouse codes: **{grouped_df['Cleaned Warehouse Code'].nunique()}**")

#             # Show result
#             st.subheader("🔍 Sample Results")
#             st.dataframe(grouped_df[[warehouse_code_col, warehouse_name_col, address_col, "Cleaned Warehouse Code", "Warehouse Match Count", "Raw Warehouse Match Count", "Match Check"]].head(50))

#             # Download
#             output = BytesIO()
#             grouped_df.drop(columns=["assigned"]).to_excel(output, index=False, engine="openpyxl")
#             st.download_button(
#                 label="📥 Download Cleaned Data",
#                 data=output.getvalue(),
#                 file_name="cleaned_warehouse_code.xlsx",
#                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#             )

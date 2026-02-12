# import pandas as pd
# import xlsxwriter

# def build_and_export_excel(template_df, datainfo_df, dropdown_df, output_file="template_attributs.xlsx"):
#     """
#     Exporte les DataFrames (template, datainfo, dropdowns) vers un fichier Excel
#     avec : tableau natif stylé, menus déroulants, commentaires sur headers, coloration "Required".
#     """
#     with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
#         template_df.to_excel(writer, sheet_name="Template", index=False)
#         datainfo_df.to_excel(writer, sheet_name="DataInfo", index=False)
#         dropdown_df.to_excel(writer, sheet_name="ListOfValues", index=False)

#         workbook = writer.book
#         ws_template = writer.sheets["Template"]
#         ws_datainfo = writer.sheets["DataInfo"]
#         ws_dropdown = writer.sheets["ListOfValues"]

#         # --- Ajout des tableaux natifs avec style pour chaque onglet ---
#         ws_template.add_table(
#             0, 0, len(template_df), len(template_df.columns) - 1,
#             {
#                 "name": "TemplateTable",
#                 "style": "Table Style Medium 2",
#                 "columns": [{"header": col} for col in template_df.columns]
#             }
#         )
#         ws_datainfo.add_table(
#             0, 0, len(datainfo_df), len(datainfo_df.columns) - 1,
#             {
#                 "name": "DataInfoTable",
#                 "style": "Table Style Medium 3",
#                 "columns": [{"header": col} for col in datainfo_df.columns]
#             }
#         )
#         ws_dropdown.add_table(
#             0, 0, len(dropdown_df), len(dropdown_df.columns) - 1,
#             {
#                 "name": "ListOfValuesTable",
#                 "style": "Table Style Medium 5",
#                 "columns": [{"header": col} for col in dropdown_df.columns]
#             }
#         )

#         # --- Appliquer le format couleur sur les colonnes fixes (après add_table) ---
#         fixed_cols = [
#             "Channel Full Category Path", "Product Id", "Offer Code", "EAN", "Name", "Description", "Catalog Id"
#         ]
#         fixed_format = workbook.add_format({
#             "bg_color": "#eaedf6",
#             "font_color": "#000000",
#             "align": "left",
#             "valign": "vcenter"
#         })

#         for col_name in fixed_cols:
#             if col_name in template_df.columns:
#                 col_idx = template_df.columns.get_loc(col_name)
#                 # On commence à row=1 pour ne pas toucher au header du tableau
#                 for row_idx in range(1, len(template_df) + 1):
#                     ws_template.write(row_idx, col_idx, template_df.iloc[row_idx - 1, col_idx], fixed_format)

#         # --- Ajout des commentaires dynamiques sur headers attributs dynamiques ---
#         datainfo_map = {
#             f"{row['Attribute Name']} | {row['Channel Attribute Id']}": (
#                 str(row.get("Type Value", "")),
#                 str(row.get("Status", "")),
#                 str(row.get("Attribute Description", ""))
#             )
#             for _, row in datainfo_df.iterrows()
#         }
#         for col_idx, col_name in enumerate(template_df.columns):
#             if col_name in datainfo_map:
#                 type_value, status, description = datainfo_map[col_name]
#                 comment = (
#                     f"Type de valeur: {type_value}\n"
#                     f"Statut : {status}\n"
#                     f"Description : {description}"
#                 )
#                 ws_template.write_comment(
#                     0, col_idx,
#                     comment,
#                     {
#                         "x_scale": 3,
#                         "y_scale": 3,
#                         "color": "#eaedf6",
#                         "font": "Calibri",
#                         "font_size": 10,
#                         "visible": False,
#                         "border": 0.5
#                     }
#                 )

#         # --- Menus déroulants sur attributs de type liste ---
#         id_to_listcode = {
#             row["Channel Attribute Id"]: row["Attribute Value List Code"]
#             for _, row in datainfo_df[datainfo_df["Attribute Value List Code"].notnull()].iterrows()
#         }
#         id_to_label = {
#             row["Channel Attribute Id"]: f"{row['Attribute Name']} | {row['Channel Attribute Id']}"
#             for _, row in datainfo_df[datainfo_df["Attribute Value List Code"].notnull()].iterrows()
#         }
#         label_to_listcode = {
#             id_to_label[attr_id]: list_code
#             for attr_id, list_code in id_to_listcode.items()
#         }
#         for col_idx, col_name in enumerate(template_df.columns):
#             if col_name in label_to_listcode:
#                 list_code = label_to_listcode[col_name]
#                 if list_code in dropdown_df.columns:
#                     col_values = dropdown_df[list_code].dropna()
#                     if len(col_values) == 0:
#                         continue
#                     col_excel = xlsxwriter.utility.xl_col_to_name(dropdown_df.columns.get_loc(list_code))
#                     first_row = 1  # Données à partir de la 2e ligne (ligne 1 = header)
#                     list_start_row = first_row + 1
#                     list_end_row = list_start_row + len(col_values) - 1
#                     dropdown_range = f"ListOfValues!${col_excel}${list_start_row}:${col_excel}${list_end_row}"

#                     ws_template.data_validation(
#                         first_row=first_row,
#                         last_row=first_row + len(template_df) - 1,
#                         first_col=col_idx,
#                         last_col=col_idx,
#                         options={
#                             "validate": "list",
#                             "source": dropdown_range
#                         }
#                     )

#         # --- Coloration des cellules "Required" du tableau uniquement ---
#         id_to_label_full = {
#             row["Channel Attribute Id"]: f"{row['Attribute Name']} | {row['Channel Attribute Id']}"
#             for _, row in datainfo_df.iterrows()
#         }
#         required_cols = [
#             id_to_label_full[row["Channel Attribute Id"]]
#             for _, row in datainfo_df.iterrows()
#             if str(row["Status"]).strip().lower() == "required" and row["Channel Attribute Id"] in id_to_label_full
#         ]
#         required_format = workbook.add_format({"bg_color": "#ffe1db", "font_color": "#000000", "align": "left", "valign": "vcenter"})
#         for col_name in required_cols:
#             if col_name in template_df.columns:
#                 col_idx = template_df.columns.get_loc(col_name)
#                 for row_idx in range(1, len(template_df) + 1):  # 1 = première ligne de données
#                     ws_template.write(row_idx, col_idx, template_df.iloc[row_idx - 1, col_idx], required_format)

#     print(f"\n✅ Fichier Excel généré avec styles tableaux, menus déroulants, commentaires et coloration des 'Required' : {output_file}")

import pandas as pd
import xlsxwriter
import numpy as np
import math

def build_and_export_excel(template_df, datainfo_df, dropdown_df, output_file="template_attributs.xlsx"):
    """
    Exporte les DataFrames (template, datainfo, dropdowns) vers un fichier Excel
    avec : tableau natif stylé, menus déroulants, commentaires sur headers, coloration "Required".
    """

    # Helper pour écrire en évitant l'erreur NAN/INF
    def safe_write(ws, row, col, val, cell_format=None):
        """
        Ecrit val dans la cellule (row, col). Si val est NaN/Inf, on écrit une chaîne vide.
        """
        # pandas.isna traite aussi les numpy.nan
        if pd.isna(val):
            ws.write(row, col, '', cell_format)
            return
        # float('inf') / -inf
        if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
            ws.write(row, col, '', cell_format)
            return
        # sinon écriture normale
        ws.write(row, col, val, cell_format)

    # Optionnel : demander à xlsxwriter d'écrire NaN/Inf comme erreurs Excel
    # (on remplace déjà les valeurs par des chaînes vides via safe_write,
    #  mais ceci est une protection supplémentaire si d'autres API écrivent directement)
    engine_kwargs = {"options": {"nan_inf_to_errors": True}}

    with pd.ExcelWriter(output_file, engine="xlsxwriter", engine_kwargs=engine_kwargs) as writer:
        # On écrit les DataFrames tels quels (les cellules potentiellement NaN seront gérées
        # plus tard lors des writes formatés par safe_write). to_excel gère NaN en laissant vide.
        template_df.to_excel(writer, sheet_name="Template", index=False)
        datainfo_df.to_excel(writer, sheet_name="DataInfo", index=False)
        dropdown_df.to_excel(writer, sheet_name="ListOfValues", index=False)

        workbook = writer.book
        ws_template = writer.sheets["Template"]
        ws_datainfo = writer.sheets["DataInfo"]
        ws_dropdown = writer.sheets["ListOfValues"]

        # --- Ajout des tableaux natifs avec style pour chaque onglet ---
        ws_template.add_table(
            0, 0, len(template_df), len(template_df.columns) - 1,
            {
                "name": "TemplateTable",
                "style": "Table Style Medium 2",
                "columns": [{"header": col} for col in template_df.columns]
            }
        )
        ws_datainfo.add_table(
            0, 0, len(datainfo_df), len(datainfo_df.columns) - 1,
            {
                "name": "DataInfoTable",
                "style": "Table Style Medium 3",
                "columns": [{"header": col} for col in datainfo_df.columns]
            }
        )
        ws_dropdown.add_table(
            0, 0, len(dropdown_df), len(dropdown_df.columns) - 1,
            {
                "name": "ListOfValuesTable",
                "style": "Table Style Medium 5",
                "columns": [{"header": col} for col in dropdown_df.columns]
            }
        )

        # --- Appliquer le format couleur sur les colonnes fixes (après add_table) ---
        fixed_cols = [
            "Channel Full Category Path", "Product Id", "Offer Code", "EAN", "Name", "Description", "Catalog Id"
        ]
        fixed_format = workbook.add_format({
            "bg_color": "#eaedf6",
            "font_color": "#000000",
            "align": "left",
            "valign": "vcenter"
        })

        for col_name in fixed_cols:
            if col_name in template_df.columns:
                col_idx = template_df.columns.get_loc(col_name)
                # On commence à row=1 pour ne pas toucher au header du tableau
                for row_idx in range(1, len(template_df) + 1):
                    # récupère la valeur depuis le DataFrame original, mais écrit via safe_write
                    val = template_df.iloc[row_idx - 1, col_idx]
                    safe_write(ws_template, row_idx, col_idx, val, fixed_format)

        # --- Ajout des commentaires dynamiques sur headers attributs dynamiques ---
        datainfo_map = {
            f"{row['Attribute Name']} | {row['Channel Attribute Id']}": (
                str(row.get("Type Value", "")),
                str(row.get("Status", "")),
                str(row.get("Attribute Description", ""))
            )
            for _, row in datainfo_df.iterrows()
        }
        for col_idx, col_name in enumerate(template_df.columns):
            if col_name in datainfo_map:
                type_value, status, description = datainfo_map[col_name]
                comment = (
                    f"Type de valeur: {type_value}\n"
                    f"Statut : {status}\n"
                    f"Description : {description}"
                )
                ws_template.write_comment(
                    0, col_idx,
                    comment,
                    {
                        "x_scale": 3,
                        "y_scale": 3,
                        "color": "#eaedf6",
                        "font": "Calibri",
                        "font_size": 10,
                        "visible": False,
                        "border": 0.5
                    }
                )

        # --- Menus déroulants sur attributs de type liste ---
        id_to_listcode = {
            row["Channel Attribute Id"]: row["Attribute Value List Code"]
            for _, row in datainfo_df[datainfo_df["Attribute Value List Code"].notnull()].iterrows()
        }
        id_to_label = {
            row["Channel Attribute Id"]: f"{row['Attribute Name']} | {row['Channel Attribute Id']}"
            for _, row in datainfo_df[datainfo_df["Attribute Value List Code"].notnull()].iterrows()
        }
        label_to_listcode = {
            id_to_label[attr_id]: list_code
            for attr_id, list_code in id_to_listcode.items()
        }
        for col_idx, col_name in enumerate(template_df.columns):
            if col_name in label_to_listcode:
                list_code = label_to_listcode[col_name]
                if list_code in dropdown_df.columns:
                    col_values = dropdown_df[list_code].dropna()
                    if len(col_values) == 0:
                        continue
                    col_excel = xlsxwriter.utility.xl_col_to_name(dropdown_df.columns.get_loc(list_code))
                    first_row = 1  # Données à partir de la 2e ligne (ligne 1 = header)
                    list_start_row = first_row + 1
                    list_end_row = list_start_row + len(col_values) - 1
                    dropdown_range = f"ListOfValues!${col_excel}${list_start_row}:${col_excel}${list_end_row}"

                    ws_template.data_validation(
                        first_row=first_row,
                        last_row=first_row + len(template_df) - 1,
                        first_col=col_idx,
                        last_col=col_idx,
                        options={
                            "validate": "list",
                            "source": dropdown_range
                        }
                    )

        # --- Coloration des cellules "Required" du tableau uniquement ---
        id_to_label_full = {
            row["Channel Attribute Id"]: f"{row['Attribute Name']} | {row['Channel Attribute Id']}"
            for _, row in datainfo_df.iterrows()
        }
        required_cols = [
            id_to_label_full[row["Channel Attribute Id"]]
            for _, row in datainfo_df.iterrows()
            if str(row["Status"]).strip().lower() == "required" and row["Channel Attribute Id"] in id_to_label_full
        ]
        required_format = workbook.add_format({"bg_color": "#ffe1db", "font_color": "#000000", "align": "left", "valign": "vcenter"})
        for col_name in required_cols:
            if col_name in template_df.columns:
                col_idx = template_df.columns.get_loc(col_name)
                for row_idx in range(1, len(template_df) + 1):  # 1 = première ligne de données
                    val = template_df.iloc[row_idx - 1, col_idx]
                    safe_write(ws_template, row_idx, col_idx, val, required_format)

    print(f"\n✅ Fichier Excel généré avec styles tableaux, menus déroulants, commentaires et coloration des 'Required' : {output_file}")



import pandas as pd
import time

def build_template_dataframe(product_df, selected_attributes, catalog_id):
    """
    Construit le DataFrame final du template à partir des produits et des attributs sélectionnés.
    Prend en compte les valeurs overrides (prioritaires), sinon les mappings.
    """
    template_columns_mapping = {
        f"{row['Attribute Name']} | {row['Channel Attribute Id']}": row["Channel Attribute Id"]
        for _, row in selected_attributes.iterrows()
    }
    template_data = []
    for _, product in product_df.iterrows():
        row = {
            "Catalog Id": catalog_id,
            "Product Id": product.get("Product Id"),
            "Ean": product.get("Ean") or "",
            "Sku": product.get("Product Sku"),
            "Product Title": product.get("Product Title")
        }
        mapping = product.get("attributeMappingValue", {})
        overrides = product.get("overrides", {})
        for column_name, attribute_id in template_columns_mapping.items():
            value = None
            override_obj = overrides.get(attribute_id)
            if isinstance(override_obj, dict):
                value = override_obj.get("override")
            if not value:
                mapping_obj = mapping.get(attribute_id)
                if isinstance(mapping_obj, dict):
                    value = mapping_obj.get("attributeMappingValue")
            row[column_name] = value if value is not None else ""
        template_data.append(row)
    return pd.DataFrame(template_data)

def build_dropdown_dataframe(client, catalog_id, selected_attributes_df):
    """
    Construit l'onglet ListOfValues (menus déroulants) pour tous les attributs de type liste à éditer.
    Retourne un DataFrame, chaque colonne correspondant à une liste de valeurs d'attribut.
    """
    df_list_attributes = selected_attributes_df[selected_attributes_df["Attribute Value List Code"].notnull()]
    attribute_mapping = {
        row["Channel Attribute Id"]: row["Attribute Value List Code"]
        for _, row in df_list_attributes.iterrows()
    }
    value_dict = {}
    for attribute_id, value_list_code in attribute_mapping.items():
        response = client.get_attribute_value_list(catalog_id, attribute_id)
        if not response:
            continue
        values = response.get("channelAttributeValuesWithMapping", [])
        value_dict[value_list_code] = [
            f"{v.get('code')} | {v.get('label')}"
            for v in values
            if v.get("label") and v.get("code")
        ]
        time.sleep(0.1)  # pour éviter d'abuser de l'API
    # Chaque colonne = une liste de valeurs, lignes = valeur ou None
    return pd.DataFrame({k: pd.Series(v) for k, v in value_dict.items()})

def build_datainfo_dataframe(full_attribute_df):
    """
    Construit l'onglet DataInfo à partir du DataFrame des attributs (selected_df ou datainfo_df).
    Contient toutes les colonnes métier nécessaires pour affichage, export ou mapping.
    """
    keep_cols = [
        "Channel Attribute Id",
        "Attribute Name",
        "Attribute Description",
        "Status",
        "Type Value",
        "Attribute Value List Code",
        "Is Mapped"
    ]
    # Prend toutes les colonnes présentes dans full_attribute_df qui sont dans keep_cols
    keep_cols = [col for col in keep_cols if col in full_attribute_df.columns]
    return full_attribute_df[keep_cols].drop_duplicates().reset_index(drop=True)

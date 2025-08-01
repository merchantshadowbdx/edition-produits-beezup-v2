from beezup.client import BeezUPClient
import pandas as pd

def get_store_and_channel_ids(client: BeezUPClient, catalog_id: str):
    """
    Récupère store_id et channel_id depuis un channelCatalog.
    """
    data = client.get_channel_catalog_data(catalog_id)
    if data:
        return data.get("storeId"), data.get("channelId")
    return None, None

def get_catalog_column_id(columns: list, column_name: str):
    """
    Cherche l'ID d'une colonne dans la liste des colonnes du catalogue.
    """
    for column in columns:
        if column.get("catalogColumnName") == column_name:
            return column.get("id")
    return None

def extract_products(client: BeezUPClient, catalog_id: str, eans: list):
    """
    Extrait tous les produits (productInfos) d'un canal à partir d'une liste d'EANs.
    """
    products = []
    page = 1
    while True:
        payload = {
            "pageNumber": page,
            "pageSize": 1000,
            "criteria": {
                "logic": "cumulative",
                "exist": True,
                "uncategorized": False,
                "excluded": False,
                "disabled": False
            },
            "productFilters": {
                "channelEans": eans
            }
        }
        response = client.get_products(catalog_id, payload)
        if not response:
            break
        products += response.get("productInfos", [])
        page_count = response.get("paginationResult", {}).get("pageCount", 1)
        if page >= page_count:
            break
        page += 1
    return products

def extract_octopia_product_fields(client: BeezUPClient, store_id: str, column_ids: dict, product_ids: list) -> pd.DataFrame:
    """
    Extrait les champs fixes pour chaque productId (via /catalogs/{store_id}/products/list).
    Args:
        client: BeezUPClient
        store_id: str
        column_ids: dict {nom_champ: column_id}
        product_ids: list de productId
    Returns:
        DataFrame (une ligne par produit, une colonne par champ demandé)
    """
    data = []
    page = 1
    while True:
        payload = {
            "pageNumber": page,
            "pageSize": 100,
            "exists": "true",
            "columnIdList": list(column_ids.values()),
            "productIdList": product_ids
        }
        response = client.get_product_values(store_id, payload)
        if not response:
            break
        products = response.get("products", [])
        page_count = response.get("paginationResult", {}).get("pageCount", 1)
        for product in products:
            product_id = product.get("productId")
            values = product.get("values", {})
            row = {"Product Id": product_id}
            for name, col_id in column_ids.items():
                # Recherche insensible à la casse
                row[name] = next((v for k, v in values.items() if k.lower() == col_id.lower()), "")
            data.append(row)
        if page >= page_count:
            break
        page += 1
    return pd.DataFrame(data)

def extract_channel_paths(client: BeezUPClient, catalog_id: str, categ3_codes: list):
    """
    Extrait tous les chemins canal correspondant aux catégories Octopia niveau 3 utilisées.
    """
    response = client.get_category_mapping_data(catalog_id)
    if not response:
        return []
    path_set = set()
    codes_set = set(categ3_codes)
    for config in response.get("channelCatalogCategoryConfigurations", []):
        if any(code in config.get("catalogCategoryPath", []) for code in codes_set):
            path = config.get("channelCategoryPath", [])
            formatted = " > ".join(path)
            if formatted:
                path_set.add(formatted)
    return sorted(path_set)

def extract_octopia_channel_mapping(client: BeezUPClient, catalog_id: str, categ3_codes: list) -> pd.DataFrame:
    """
    Crée un mapping code Octopia <-> chemin complet canal de vente.
    """
    response = client.get_category_mapping_data(catalog_id)
    if not response:
        return pd.DataFrame()
    codes_set = set(categ3_codes)
    mapping_rows = []
    for config in response.get("channelCatalogCategoryConfigurations", []):
        catalog_path = config.get("catalogCategoryPath", [])
        channel_path = config.get("channelCategoryPath", [])
        formatted_path = " > ".join(channel_path)
        for code in catalog_path:
            if code in codes_set:
                mapping_rows.append({
                    "Category Code": code,
                    "Channel Full Category Path": formatted_path
                })
    return pd.DataFrame(mapping_rows).drop_duplicates()

def extract_channel_attributes(client: BeezUPClient, catalog_id: str, channel_paths: list):
    """
    Extrait tous les attributs canal de vente pour les catégories concernées.
    """
    response = client.get_channel_attributes_data(catalog_id)
    if not response:
        return pd.DataFrame()
    channel_paths_set = set(channel_paths)
    channel_paths_set.add("Cross Categories")
    attributes = []
    for category in response:
        if category.get("channelFullCategoryPath") not in channel_paths_set:
            continue
        for attr in category.get("attributes", []):
            attributes.append({
                "Channel Full Category Path": category.get("channelFullCategoryPath"),
                "Channel Attribute Id": attr.get("channelAttributeId"),
                "Attribute Name": attr.get("attributeName"),
                "Attribute Code": attr.get("attributeCode"),
                "Attribute Description": attr.get("attributeDescription"),
                "Status": attr.get("status"),
                "Type Value": attr.get("typeValue"),
                "Attribute Value List Code": attr.get("attributeValueListCode"),
                "Default Value": attr.get("defaultValue"),
                "Is Mapped": "Yes" if attr.get("catalogColumnId") else "No"
            })
    return pd.DataFrame(attributes)

import streamlit as st
import tempfile
from datetime import datetime

from beezup.client import BeezUPClient
from beezup.extractor import *
from beezup.formatter import *
from beezup.builder import build_and_export_excel

# ---------- SIDEBAR ---------- #
with st.sidebar:
    st.title("Paramètres")
    api_key = st.text_input("*Clé API BeezUP*", type="password", key="api_key")
    store_name = st.text_input("*Nom de la boutique*", key="store_name")
    catalog_id = st.text_input("*Channel Catalog ID*", key="catalog_id")

    if st.button("🔄 Réinitialiser l'application", key="reset_app"):
        api_key_val = st.session_state.get("api_key", "")
        catalog_id_val = st.session_state.get("catalog_id", "")

        # Incrémente la clé du widget text_area pour forcer un “reset” du widget
        current = st.session_state.get("eans_text_key", "eans_text_0")
        idx = int(current.split("_")[-1]) + 1

        st.session_state.clear()
        st.session_state["api_key"] = api_key_val
        st.session_state["catalog_id"] = catalog_id_val
        st.session_state["eans_text_key"] = f"eans_text_{idx}"
        st.rerun()

# ---------- ONGLETS ---------- #
tab1, tab2 = st.tabs(["Générer un template", "Éditer les produits"])

# Nettoyer les statuts
def clear_after(step):
    clear_list = [
        "client", "store_id", "channel_id", "product_df", "attribute_df", "merged_df",
        "eans_validated", "attrs_validated", "selected_df", "template_generated",
        "template_df", "dropdown_df", "datainfo_df"
    ]
    for s in clear_list:
        if s in st.session_state and clear_list.index(s) > clear_list.index(step):
            del st.session_state[s]

# ---------- TAB1 : GENERER UN TEMPLATE ---------- #
with tab1:
    st.title("Génération du template produits")

    # --- Étape 1 : Saisie EANs
    with st.container(border=True):
        st.subheader("\u2776 EANs à traiter")

        # Initialise la clé dynamique si besoin (juste avant le text_area)
        if "eans_text_key" not in st.session_state:
            st.session_state["eans_text_key"] = "eans_text_0"

        eans_text = st.text_area(
            "*Collez vos EANs (un par ligne)*",
            key=st.session_state["eans_text_key"]
        )

        # Saisie des EANs
        eans = [ean.strip() for ean in eans_text.splitlines() if ean.strip()]
        valider_eans = st.button("Valider les EANs", key="validate_eans")

        if valider_eans:
            if api_key and catalog_id and eans:
                with st.spinner("Génération des listes d'attributs en cours..."):

                    # Création du BeezUPClient et extraction des IDs
                    client = BeezUPClient(api_key)
                    store_id, channel_id = get_store_and_channel_ids(client, catalog_id)
                    st.session_state["client"] = client
                    st.session_state["store_id"] = store_id
                    st.session_state["channel_id"] = channel_id

                    # Extraction et création du dataframe product_df
                    product_infos = extract_products(client, catalog_id, eans)
                    all_override_keys, all_attr_mapping_keys = set(), set()

                    for prod in product_infos:
                        all_override_keys.update(prod.get("overrides", {}).keys())
                        all_attr_mapping_keys.update(prod.get("attributeMappingValue", {}).keys())

                    override_columns = sorted(list(all_override_keys))
                    attr_mapping_columns = sorted(list(all_attr_mapping_keys))
                    rows = []

                    for prod in product_infos:
                        row = {
                            "Product Id": prod.get("productId"),
                            "Offer Code": prod.get("productSku"),
                            "Name": prod.get("productTitle"),
                            "Catalog Id": catalog_id
                        }

                        for col in override_columns:
                            value = prod.get("overrides", {}).get(col, {})
                            row[col] = value.get("override") if isinstance(value, dict) else ""

                        for col in attr_mapping_columns:
                            value = prod.get("attributeMappingValue", {}).get(col, {})
                            row[col] = f"{value.get('attributeMappingValue')} | {value.get('catalogValue')}" if isinstance(value, dict) else ""

                        rows.append(row)

                    product_df = pd.DataFrame(rows)

                    # Extraction des column_ids des attributs côté catalogue
                    catalog_columns = client.get_catalog_columns(store_id).get("catalogColumns", [])
                    categ3_column_id = get_catalog_column_id(catalog_columns, "categ3Code")
                    ean_column_id = get_catalog_column_id(catalog_columns, "ean")
                    description_column_id = get_catalog_column_id(catalog_columns, "description")

                    column_ids = {
                        "Category Code": categ3_column_id,
                        "EAN": ean_column_id,
                        "Description": description_column_id
                    }

                    # Extraction et création du dataframe octopia_df
                    product_ids = product_df["Product Id"].tolist()
                    octopia_df = extract_octopia_product_fields(client, store_id, column_ids, product_ids)

                    # Fusion des dataframes product_df et octopia_df sur la colonne "Product Id"
                    product_df["Product Id"] = product_df["Product Id"].astype(str).str.strip()
                    octopia_df["Product Id"] = octopia_df["Product Id"].astype(str).str.strip()

                    merged_df = pd.merge(
                        product_df,
                        octopia_df[["Product Id", "Category Code", "EAN", "Description"]],
                        on="Product Id",
                        how="left"
                    )

                    # Réorganisation des colonnes
                    cols_order = [
                        "Category Code", "Product Id", "Offer Code", "EAN", "Name", "Description", "Catalog Id"
                    ] + override_columns + attr_mapping_columns

                    merged_df = merged_df[[col for col in cols_order if col in merged_df.columns]]

                    # Extraction du mapping catégories Octopia <-> canal de vente
                    mapping_df = extract_octopia_channel_mapping(client, catalog_id, merged_df["Category Code"].unique())

                    # Remplacement de la colonne "Category Code" par "Channel Full Category Path"
                    merged_df = merged_df.merge(mapping_df, on="Category Code", how="left")
                    merged_df.drop(columns=["Category Code"], inplace=True)
                    merged_df.rename(columns={"Category Code": "Channel Full Category Path"}, inplace=True)

                    cols = merged_df.columns.tolist()
                    cols.insert(0, cols.pop(cols.index("Channel Full Category Path")))
                    merged_df = merged_df[cols]

                    # Extraction et création du dataframe attribute_df
                    channel_paths = merged_df["Channel Full Category Path"].unique().tolist()
                    attribute_df = extract_channel_attributes(client, catalog_id, channel_paths)

                    # Mise à jour des session_state
                    st.session_state["product_df"] = product_df
                    st.session_state["merged_df"] = merged_df
                    st.session_state["attribute_df"] = attribute_df
                    st.session_state["override_columns"] = override_columns
                    st.session_state["attr_mapping_columns"] = attr_mapping_columns
                    st.session_state["eans_validated"] = True
                    clear_after("eans_validated")
            else:
                st.error("Merci de renseigner la clé API, le Channel Catalog ID et au moins un EAN.")
                st.session_state["eans_validated"] = False

    # --- Étape 2 : Sélection attributs
    if st.session_state.get("eans_validated", False) and "attribute_df" in st.session_state:
        # Génération de la liste des attributs éditables
        attribute_df = st.session_state["attribute_df"].copy()
        attribute_df["display_label"] = (
                attribute_df["Attribute Name"] + " [" + attribute_df["Status"].fillna("") + "]"
        )

        with st.container(border=True):
            st.subheader("\u2777 Choix des attributs à éditer")

            # Création de  la liste des Channel Attribute Ids sélectionnés par les pills
            pills_choice = st.pills(
                "*Sélectionner les attributs selon leur statut*",
                options=["Required", "Recommended", "Optional"],
                selection_mode="multi",
                default=st.session_state.get("pills_choice", []),
                key="pills_choice"
            )
            selected_ids_pills = set(
                attribute_df.loc[
                    attribute_df["Status"].fillna("").str.capitalize().isin([p.capitalize() for p in pills_choice]),
                    "Channel Attribute Id"
                ]
            )

            # Dans le multiselect, **propose uniquement** les display_label dont Channel Attribute Id N'EST PAS déjà dans selected_ids_pills
            choices = (
                attribute_df[["Attribute Name", "Channel Attribute Id", "Status", "display_label"]]
                .drop_duplicates()
                .reset_index(drop=True)
            )
            options = [
                row["display_label"]
                for _, row in choices.iterrows()
                if row["Channel Attribute Id"] not in selected_ids_pills
            ]
            display_label_to_id = dict(zip(choices["display_label"], choices["Channel Attribute Id"]))

            selected_labels = st.multiselect(
                "*Sélectionner un ou plusieurs attributs à éditer (en plus de la sélection par statut)*",
                options=options,
                key="selected_display_names"
            )

            selected_ids_hand = set(display_label_to_id[label] for label in selected_labels)

            # Sélection finale = ids des pills + ids manuels
            selected_ids = selected_ids_hand.union(selected_ids_pills)

            # Reconstruction de selected_df
            selected_df = attribute_df[attribute_df["Channel Attribute Id"].isin(selected_ids)].drop_duplicates(
                subset=["Channel Attribute Id"])
            st.session_state["selected_df"] = selected_df

            if selected_df.empty and st.session_state.get("attrs_validated", False):
                # Si plus aucun attribut sélectionné, on masque l'étape 3 automatiquement
                st.session_state["attrs_validated"] = False

            st.caption(f"*{len(selected_ids)} attribut(s) sélectionné(s)*")
            st.dataframe(selected_df[["Attribute Name", "Status"]], hide_index=True)

            if st.button("Valider la sélection d'attributs", key="validate_attrs"):
                if len(selected_df) > 0:
                    st.session_state["attrs_validated"] = True
                else:
                    st.session_state["attrs_validated"] = False
                    st.warning("Merci de sélectionner au moins un attribut.")

    # --- Étape 3 : Génération et affichage du template
    selected_df = st.session_state.get("selected_df")
    if st.session_state.get("attrs_validated", False) and selected_df is not None and not selected_df.empty:
        with st.container(border=True):
            st.subheader("\u2778 Génération et export du template")
            with st.spinner("Génération du template en cours..."):
                # Récupération des session_states
                merged_df = st.session_state["merged_df"]
                selected_df = st.session_state["selected_df"]
                override_columns = st.session_state["override_columns"]
                attr_mapping_columns = st.session_state["attr_mapping_columns"]

                # Pipeline de génération du template
                fixed_columns = [
                    "Channel Full Category Path", "Product Id", "Offer Code", "EAN", "Name", "Description", "Catalog Id"
                ]
                selected_attr_cols = [row["Channel Attribute Id"] for _, row in selected_df.iterrows()]
                attr_mapping_to_keep = [col for col in attr_mapping_columns if col in selected_attr_cols]
                attr_mapping_to_drop = [col for col in attr_mapping_columns if col not in selected_attr_cols]
                merged_df_ = merged_df.drop(columns=[col for col in attr_mapping_to_drop if col in merged_df.columns])

                final_cols = (
                    fixed_columns +
                    override_columns +
                    attr_mapping_to_keep +
                    [col for col in selected_attr_cols if col not in override_columns + attr_mapping_to_keep]
                )

                for col in final_cols:
                    if col not in merged_df_.columns:
                        merged_df_[col] = ""

                template_df = merged_df_[[col for col in final_cols if col in merged_df_.columns]]

                # Renommage des colonnes pour plus de clarté lors du remplissage
                id_to_label = {
                    row["Channel Attribute Id"]: f"{row['Attribute Name']} | {row['Channel Attribute Id']}"
                    for _, row in selected_df.iterrows()
                }
                template_df = template_df.rename(columns=id_to_label)

                # Mise à jour des session_states
                client = st.session_state["client"]

                # Génération du DataFrame des listes de valeurs
                dropdown_df = build_dropdown_dataframe(client, catalog_id, selected_df)

                # Génération du DataFrame des infos attributs
                datainfo_df = build_datainfo_dataframe(selected_df)

                # Mise à jour des session_states
                st.session_state["template_df"] = template_df
                st.session_state["dropdown_df"] = dropdown_df
                st.session_state["datainfo_df"] = datainfo_df
                st.session_state["template_generated"] = True

            # Affichage du template
            st.dataframe(template_df, use_container_width=True, hide_index=True)

            # Export du template au format Excel
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmpfile:
                build_and_export_excel(
                    template_df,
                    datainfo_df,
                    dropdown_df,
                    output_file=tmpfile.name
                )
                tmpfile.seek(0)

                # === Calcul du nom de fichier personnalisé ===
                today_str = datetime.now().strftime("%Y-%m-%d")
                store_name = st.session_state.get("store_name", "")
                if not store_name:
                    store_name_safe = "no_name"
                else:
                    store_name_safe = "".join(c for c in store_name if c.isalnum() or c in ("_", "-")).strip().lower()
                nb_products = len(template_df)
                filename = f"template_{store_name_safe}_{today_str} [{nb_products} products].xlsx"

                st.download_button(
                    label="Télécharger le template Excel",
                    data=tmpfile.read(),
                    file_name=filename
                )

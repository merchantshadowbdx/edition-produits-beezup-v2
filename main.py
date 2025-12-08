import streamlit as st
import tempfile
from datetime import datetime

from beezup.client import BeezUPClient
from beezup.extractor import *
from beezup.formatter import *
from beezup.builder import build_and_export_excel

st.set_page_config(page_title="Edition produits BeezUP V2", layout="wide", page_icon="🐝")

# ---------- SIDEBAR ---------- #
with st.sidebar:
    st.image("décembre.png", width="content", caption="Joyeuses fêtes")
    st.title("Paramètres")
    api_key = st.text_input("*Clé API BeezUP*", type="password", key="api_key")
    store_name = st.text_input("*Nom de la boutique*", key="store_name")
    catalog_id = st.text_input("*Channel Catalog ID*", key="catalog_id")

    if st.button("\u21bb Réinitialiser l'application", key="reset_app"):
        api_key_val = st.session_state.get("api_key", "")
        catalog_id_val = st.session_state.get("catalog_id", "")
        store_name_val = st.session_state.get("store_name", "")
    
        # 🔹 Incrémenter les clés dynamiques pour forcer les resets des text_area
        eans_key = st.session_state.get("eans_text_key", "eans_text_0")
        eans_idx = int(eans_key.split("_")[-1]) + 1
    
        attr_key = st.session_state.get("attr_text_key", "attr_text_0")
        attr_idx = int(attr_key.split("_")[-1]) + 1
    
        # 🔹 Réinitialiser le session_state en conservant les infos importantes
        st.session_state.clear()
        st.session_state["api_key"] = api_key_val
        st.session_state["catalog_id"] = catalog_id_val
        st.session_state["store_name"] = store_name_val
        st.session_state["eans_text_key"] = f"eans_text_{eans_idx}"
        st.session_state["attr_text_key"] = f"attr_text_{attr_idx}"
    
        st.rerun()

# ---------- ONGLETS ---------- #
tab1, tab2, tab3 = st.tabs(["Générer un template", "Éditer les produits", "Mapper les attributs"])

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
        valider_eans = st.button("\u2713 Valider les EANs", key="validate_eans")

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

                    # Ajout pour extraction des images
                    # Images 1..6 (on n’ajoute que celles réellement trouvées)
                    for i in range(1, 7):
                        img_id = get_catalog_column_id(catalog_columns, f"imageUrl{i}")
                        if img_id:  # si la colonne image{i} existe dans ce catalogue
                            column_ids[f"Image {i}"] = img_id

                    # Extraction et création du dataframe octopia_df
                    product_ids = product_df["Product Id"].tolist()
                    octopia_df = extract_octopia_product_fields(client, store_id, column_ids, product_ids)

                    # Fusion des dataframes product_df et octopia_df sur la colonne "Product Id"
                    product_df["Product Id"] = product_df["Product Id"].astype(str).str.strip()
                    octopia_df["Product Id"] = octopia_df["Product Id"].astype(str).str.strip()

                    # Ajout pour extraction des images
                    # Colonnes fixes demandées depuis column_ids (en conservant l’ordre “Category/EAN/Description” devant)
                    base_fixed = ["Category Code", "EAN", "Description"]
                    image_fixed = [f"Image {i}" for i in range(1, 7) if f"Image {i}" in octopia_df.columns]
                    octo_cols = ["Product Id"] + base_fixed + image_fixed

                    merged_df = pd.merge(
                        product_df,
                        octopia_df[octo_cols],
                        # octopia_df[["Product Id", "Category Code", "EAN", "Description"]],
                        on="Product Id",
                        how="left"
                    )

                    # Réorganisation : colonnes fixes + overrides + mappings
                    cols_order = (
                            ["Category Code", "Product Id", "Offer Code", "EAN", "Name", "Description", "Catalog Id"] +
                            image_fixed +  # on insère ici les images fixes trouvées
                            override_columns +
                            attr_mapping_columns
                    )

                    # # Réorganisation des colonnes
                    # cols_order = [
                    #     "Category Code", "Product Id", "Offer Code", "EAN", "Name", "Description", "Catalog Id"
                    # ] + override_columns + attr_mapping_columns

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
        # 1) Base d'attributs + normalisation
        attribute_df = st.session_state["attribute_df"].copy()
        attribute_df["Status"] = attribute_df["Status"].fillna("").str.strip().str.capitalize()
        attribute_df["Channel Full Category Path"] = attribute_df["Channel Full Category Path"].fillna("")

        # # 👉 Filtre pour exclure les attributs dont le nom contient "[REMOVED BY MKP]"
        # attribute_df = attribute_df[~attribute_df["Attribute Name"].str.contains(r"\[REMOVED BY MKP\]", case=False, na=False)]
    
        # # 2) Priorisation "catégorie spécifique" > "Cross Categories"
        # #    + à statut égal, on garde le plus restrictif: Required < Recommended < Optional
        # status_rank = {"Required": 0, "Recommended": 1, "Optional": 2, "": 3}
        # attribute_df["__is_cross"] = (attribute_df["Channel Full Category Path"] == "Cross Categories").astype(int)
        # attribute_df["__status_rank"] = attribute_df["Status"].map(status_rank).fillna(3).astype(int)

        # attribute_df = (
        #     attribute_df
        #     .sort_values(["Channel Attribute Id", "__is_cross", "__status_rank"], ascending=[True, True, True])
        #     .drop_duplicates(subset=["Channel Attribute Id"], keep="first")
        #     .reset_index(drop=True)
        # )

        # --- Nettoyage des attributs inutiles et doublons ---
        
        # 1️⃣ Supprimer les attributs dépréciés marqués [REMOVED BY MKP]
        attribute_df = attribute_df[
            ~attribute_df["Attribute Name"].str.contains(r"\[REMOVED BY MKP\]", case=False, na=False)
        ].copy()


        # 2️⃣ Identifier et résoudre les doublons sur la paire (Attribute Name, Channel Attribute Id)
        if {"Attribute Name", "Channel Attribute Id"}.issubset(attribute_df.columns):
            # -- Normalisation préventive du statut (au cas où ce ne serait pas déjà fait)
            attribute_df["Status"] = attribute_df["Status"].fillna("").astype(str).str.strip().str.capitalize()
        
            # Priorité des statuts (plus petit = plus restrictif)
            status_rank = {"Required": 0, "Recommended": 1, "Optional": 2, "": 3}
            attribute_df["__status_rank"] = attribute_df["Status"].map(status_rank).fillna(3).astype(int)
        
            # Flag : 0 = spécifique (préféré), 1 = Cross Categories (moins prioritaire)
            attribute_df["__is_cross"] = attribute_df["Channel Full Category Path"].fillna("").eq("Cross Categories").astype(int)
        
            # Tri : on veut la combinaison la plus restrictive ET spécifique en tête pour CHAQUE paire
            attribute_df = (
                attribute_df
                .sort_values(
                    by=["Attribute Name", "Channel Attribute Id", "__status_rank", "__is_cross"],
                    ascending=[True, True, True, True]
                )
                .drop_duplicates(subset=["Attribute Name", "Channel Attribute Id"], keep="first")
                .reset_index(drop=True)
            )
        
            # Nettoyage des colonnes techniques
            attribute_df.drop(columns=["__status_rank", "__is_cross"], inplace=True, errors="ignore")

        
        # # 2️⃣ Identifier les doublons sur le couple Attribute Name + Channel Attribute Id
        # if {"Attribute Name", "Channel Attribute Id"}.issubset(attribute_df.columns):
        #     # Ajout d’un flag pour prioriser les attributs spécifiques à la catégorie
        #     attribute_df["__is_cross"] = attribute_df["Channel Full Category Path"].eq("Cross Categories").astype(int)
        
        #     attribute_df = (
        #         attribute_df.sort_values(
        #             by=["Attribute Name", "Channel Attribute Id", "__is_cross"],
        #             ascending=[True, True, True]  # Cross Categories (1) passe après la catégorie spécifique (0)
        #         )
        #         # Supprime les doublons, garde la version spécifique
        #         .drop_duplicates(subset=["Attribute Name", "Channel Attribute Id"], keep="first")
        #         .reset_index(drop=True)
        #     )
        
        #     # Nettoyage du flag technique
        #     attribute_df.drop(columns=["__is_cross"], inplace=True, errors="ignore")

        # Label d'affichage
        attribute_df["display_label"] = attribute_df["Attribute Name"] + " [" + attribute_df["Status"].fillna("") + "]"

        with st.container(border=True):
            st.subheader("\u2777 Choix des attributs à éditer")

            # 3) Sélection via pills (statuts)
            pills_choice = st.pills(
                "*Sélectionner les attributs selon leur statut*",
                options=["Required", "Recommended", "Optional"],
                selection_mode="multi",
                default=st.session_state.get("pills_choice", []),
                key="pills_choice"
            )
            pills_norm = [p.capitalize() for p in pills_choice]
            selected_ids_pills = set(
                attribute_df.loc[
                    attribute_df["Status"].isin(pills_norm),
                    "Channel Attribute Id"
                ]
            )

            # 4) Multiselect : ne proposer que ce qui n'est PAS déjà choisi via pills
            #    Pour éviter les collisions de labels identiques, on passe des tuples (id, label) en "option value"
            options = [
                (row["Channel Attribute Id"], row["display_label"])
                for _, row in attribute_df.iterrows()
                if row["Channel Attribute Id"] not in selected_ids_pills
            ]

            # Valeurs par défaut conservées si encore présentes
            default_opts = [
                opt for opt in st.session_state.get("selected_attr_opts", [])
                if opt in options
            ]

            selected_attr_opts = st.multiselect(
                "*Sélectionner un ou plusieurs attributs à éditer (en plus de la sélection par statut)*",
                options=options,
                default=default_opts,
                key="selected_attr_opts",
                format_func=lambda o: o[1]  # n'affiche que le label
            )

            selected_ids_hand = {opt[0] for opt in selected_attr_opts}

            # 5) Sélection finale = pills ∪ manuel
            selected_ids = selected_ids_pills.union(selected_ids_hand)

            # Reconstruction de selected_df depuis le DF priorisé/dédupliqué
            # selected_df = (
            #     attribute_df[attribute_df["Channel Attribute Id"].isin(selected_ids)]
            #     .drop_duplicates(subset=["Channel Attribute Id"])
            # )
            selected_df = (
                attribute_df[attribute_df["Channel Attribute Id"].isin(selected_ids)]
                .drop_duplicates(subset=["Channel Attribute Id", "Attribute Name"])
                .reset_index(drop=True)
            )
            st.session_state["selected_df"] = selected_df

            # Auto-masquage de l'étape 3 si plus rien n'est sélectionné
            if selected_df.empty and st.session_state.get("attrs_validated", False):
                st.session_state["attrs_validated"] = False

            st.caption(f"*{len(selected_ids)} attribut(s) sélectionné(s)*")
            st.dataframe(selected_df[["Attribute Name", "Status"]], hide_index=True)

            # Validation pour passer à l'étape 3
            if st.button("\u2713 Valider la sélection d'attributs", key="validate_attrs"):
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

                # Ajout pour extraction des images
                # Ajouter les images présentes (dans l’ordre)
                fixed_columns += [f"Image {i}" for i in range(1, 7) if f"Image {i}" in merged_df.columns]

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

                # --- Nettoyage des doublons entre Cross Categories et catégorie spécifique ---
                # Si un attribut apparaît plusieurs fois (même Channel Attribute Id),
                # on garde la version qui n'appartient PAS à "Cross Categories"
                if "Channel Origin Category Name" in selected_df.columns:
                    selected_df = (
                        selected_df.sort_values(
                            by=["Channel Attribute Id", "Channel Origin Category Name"],
                            key=lambda col: col.eq("Cross Categories"),  # True = CrossCat → passe après
                            ascending=True
                        )
                        .drop_duplicates(subset=["Channel Attribute Id"], keep="first")
                        .reset_index(drop=True)
                    )
                
                # (optionnel) avertissement si encore des doublons
                dupes = selected_df[selected_df.duplicated(subset=["Channel Attribute Id"], keep=False)]
                if not dupes.empty:
                    st.warning(
                        f"⚠️ Certains attributs apparaissent encore en double : "
                        f"{', '.join(dupes['Attribute Name'].unique())}"
                    )
                    
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

            # --- Vérifie et corrige les doublons de colonnes avant affichage ---
            if template_df.columns.duplicated().any():
                seen = {}
                new_cols = []
                for col in template_df.columns:
                    if col not in seen:
                        seen[col] = 1
                        new_cols.append(col)
                    else:
                        seen[col] += 1
                        new_cols.append(f"{col}_{seen[col]}")  # rend unique
                template_df.columns = new_cols
                st.warning(
                    "⚠️ Des colonnes en double ont été détectées et renommées automatiquement "
                    "(ex: 'Attribut | ID_2')."
                )
            
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

# ---------- TAB2 : RÉINTÉGRER LE TEMPLATE DANS BEEZUP (baseline live + overrides conservés) ----------
with tab2:
    st.title("Réintégration du template dans BeezUP")

    # Garde-fou : paramètres obligatoires
    if not api_key or not catalog_id:
        st.info("Renseigne la **clé API** et le **Channel Catalog ID** dans la barre latérale pour continuer.")
        st.stop()

    # --- Upload du fichier template rempli ---
    with st.container(border=True):
        st.subheader("\u2776 Import du template complété")
        uploaded_template = st.file_uploader(
            "Template **rempli** (Excel)", type=["xlsx"], key="upload_filled_template_live"
        )

    # Helpers parsing / normalisation
    def extract_attr_id(col_name: str) -> str | None:
        """En-tête 'Label | AttributeId' -> AttributeId, sinon None (colonne fixe)."""
        if not isinstance(col_name, str):
            return None
        parts = [p.strip() for p in col_name.split("|", 1)]
        return parts[1] if len(parts) == 2 and parts[1] else None

    def normalize_cell_value(v) -> str:
        """'code | label' -> 'code'; sinon valeur strippée; vide -> ''."""
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        s = str(v).strip()
        if not s:
            return ""
        if "|" in s:
            return s.split("|", 1)[0].strip()
        return s

    # ---- Baseline live : on récupère l'état courant via l'API (sur base des EANs du template) ----
    def fetch_current_state_by_eans(client: BeezUPClient, catalog_id: str, eans: list[str]) -> tuple[dict, dict]:
        """
        Retourne deux dicts :
          overrides[(product_id, attribute_id)] = valeur override actuelle (normalisée)
          effective[(product_id, attribute_id)] = valeur effective actuelle (override si présent, sinon mapping) (normalisée)
        """
        from beezup.extractor import extract_products
        overrides, effective = {}, {}

        if not eans:
            return overrides, effective

        product_infos = extract_products(client, catalog_id, eans)
        for prod in product_infos:
            pid = str(prod.get("productId", "")).strip()
            if not pid:
                continue
            ov = prod.get("overrides", {}) or {}
            mp = prod.get("attributeMappingValue", {}) or {}

            # overrides
            for attr_id, obj in ov.items():
                val = normalize_cell_value(obj.get("override", "")) if isinstance(obj, dict) else ""
                if val:
                    overrides[(pid, attr_id)] = val
                    effective[(pid, attr_id)] = val

            # mapping si pas d’override
            for attr_id, obj in mp.items():
                if (pid, attr_id) in effective:
                    continue
                val = normalize_cell_value(obj.get("attributeMappingValue", "")) if isinstance(obj, dict) else ""
                if val:
                    effective[(pid, attr_id)] = val

        return overrides, effective

    def build_payloads_from_template_with_live_baseline(filled_df: pd.DataFrame) -> list[dict]:
        """
        Construit la liste des payloads à envoyer, en s'assurant que :
          - TOUTES les clés déjà en override sont renvoyées (même si identiques)
          - Les nouvelles valeurs du template écrasent celles des overrides
          - Les attributs non overridés ne sont envoyés que si différents du baseline effectif
        """
        # map colonnes -> attribute ids
        dynamic_map = {j: extract_attr_id(c) for j, c in enumerate(filled_df.columns) if extract_attr_id(c)}

        # garde-fous
        for req in ["Product Id", "Catalog Id"]:
            if req not in filled_df.columns:
                raise ValueError(f"Colonne obligatoire manquante : '{req}'")

        # baseline live à partir des EANs
        eans = []
        if "EAN" in filled_df.columns:
            eans = [str(x).strip() for x in filled_df["EAN"].dropna().astype(str).tolist() if str(x).strip()]
            eans = list(dict.fromkeys(eans))  # unique

        client = BeezUPClient(api_key)
        overrides_live, effective_live = fetch_current_state_by_eans(client, catalog_id, eans) if eans else ({}, {})

        rows_out = []
        for _, row in filled_df.iterrows():
            product_id = str(row.get("Product Id", "")).strip()
            catalog_id_row = str(row.get("Catalog Id", "")).strip()
            ean_row = str(row.get("EAN", "")).strip() if "EAN" in filled_df.columns else ""
            if not product_id or not catalog_id_row:
                continue

            # 1) point de départ : TOUTES les clés déjà en override pour ce produit
            payload = {attr_id: val for (pid, attr_id), val in overrides_live.items() if pid == product_id}

            # 2) appliquer les valeurs du template
            for j, attr_id in dynamic_map.items():
                if not attr_id:
                    continue
                colname = filled_df.columns[j]
                norm_val = normalize_cell_value(row.get(colname, None))
                if not norm_val:
                    continue

                key = (product_id, attr_id)
                base_eff = effective_live.get(key, "")
                in_override = key in overrides_live
                before = overrides_live.get(key, base_eff)

                if in_override:
                    # déjà overridé : on renvoie ce qui est dans le template (même si identique)
                    payload[attr_id] = norm_val
                else:
                    # pas d’override existant : envoyer seulement si diff de l’effectif
                    if norm_val != base_eff:
                        payload[attr_id] = norm_val

            rows_out.append({
                "EAN": ean_row,
                "Product Id": product_id,
                "Catalog Id": catalog_id_row,
                "payload": payload,
                "count": len(payload)
            })
        return rows_out

    # --- Analyse + envoi ---
    if uploaded_template is not None:
        with st.container(border=True):
            st.subheader("\u2777 Préparation et envoi des mises à jour")

            try:
                filled_df = pd.read_excel(uploaded_template)
            except Exception as e:
                st.error(f"Impossible de lire le fichier Excel : {e}")
                st.stop()

            with st.spinner("Analyse du template & récupération de l’état courant…"):
                candidates = build_payloads_from_template_with_live_baseline(filled_df)

            total_rows = len(candidates)
            total_updates = sum(c["count"] for c in candidates)
            st.write(f"- **Produits détectés** : {total_rows}")
            st.write(f"- **Attributs envoyés (total)** : {total_updates}")

            recap = pd.DataFrame([
                {"EAN": c["EAN"], "Attributs envoyés": c["count"]}
                for c in candidates
            ])
            st.dataframe(recap, hide_index=True, use_container_width=True)

            # Bouton d’envoi
            if st.button("③ Envoyer dans BeezUP", type="primary"):
                if not candidates or total_updates == 0:
                    st.warning("Aucune valeur à envoyer.")
                    st.stop()

                client = BeezUPClient(api_key)
                status_rows = []
                progress = st.progress(0.0, text="Envoi en cours…")

                for i, c in enumerate(candidates, start=1):
                    product_id = c["Product Id"]
                    ean = c["EAN"]
                    catalog_id_row = c["Catalog Id"]
                    payload = c["payload"]

                    if not payload:
                        status_rows.append({
                            "EAN": ean,
                            "Product Id": product_id,
                            "Count": 0,
                            "Status": "— (aucun changement)"
                        })
                        progress.progress(i / len(candidates))
                        continue

                    route = f"/user/channelCatalogs/{catalog_id_row}/products/{product_id}/overrides"
                    try:
                        client.put(route, data=payload)
                        status_rows.append({
                            "EAN": ean,
                            "Product Id": product_id,
                            "Count": len(payload),
                            "Status": "OK"
                        })
                    except Exception as e:
                        status_rows.append({
                            "EAN": ean,
                            "Product Id": product_id,
                            "Count": len(payload),
                            "Status": f"Erreur: {e}"
                        })

                    progress.progress(i / len(candidates))

                st.success("Envoi terminé.")
                st.dataframe(pd.DataFrame(status_rows), hide_index=True, use_container_width=True)

    else:
        with st.container(border=True):
            st.info(
                "Importe ton **template complété** (XLSX). "
                "L’application récupère l’état courant pour chaque EAN, "
                "et renvoie **tous les éditions existantes** + les changements du template."
            )


# ---------- TAB3 : MAPPER LES ATTRIBUTS NON MAPPÉS ----------
with tab3:
    st.title("🧩 Mapping automatique des attributs non mappés")

    # --- Vérification des paramètres essentiels ---
    if not api_key or not catalog_id:
        st.info("Renseigne la **clé API** et le **Channel Catalog ID** dans la barre latérale pour continuer.")
        st.stop()

    client = BeezUPClient(api_key)
    store_id, channel_id = get_store_and_channel_ids(client, catalog_id)

    with st.container(border=True):
        st.subheader("Liste des Channel Attribute Id à mapper")
        st.markdown("Colle ci-dessous la liste des **Channel Attribute Id** (un par ligne) que tu veux associer à un champ personnalisé vide.")

        # Clé dynamique pour forcer le reset du text_area
        if "attr_text_key" not in st.session_state:
            st.session_state["attr_text_key"] = "attr_text_0"
        
        attr_text = st.text_area(
            "Channel Attribute Id (un par ligne)",
            placeholder="Exemple :\n11250c20-b2c7-4c2b-b046-feedb4c6e6db\n30aa2fa3-4a47-4eee-b8a0-d63f5ef42199",
            key=st.session_state["attr_text_key"]
        )
        
        attrs_to_map = [a.strip() for a in attr_text.splitlines() if a.strip()]

        if not attrs_to_map:
            st.info("📝 Renseigne au moins un Channel Attribute Id ci-dessus.")
            st.stop()

        st.write(f"**{len(attrs_to_map)} attribut(s)** à mapper seront associés au champ personnalisé vide.")

        if st.button("Mapper les attributs", type="primary"):       
            with st.spinner("Vérification / création du champ personnalisé vide..."):
                # 1️⃣ Vérifie s’il existe déjà un champ perso vide
                custom_columns = client.get_custom_columns(store_id) or {}
                custom_id = None
                for col in custom_columns.get("customColumns", []):
                    if col.get("userColumName") == "Champ perso vide généré par API":
                        custom_id = col.get("id")
                        break
        
                # Sinon, création automatique
                if not custom_id:
                    custom_id = client.create_custom_column(store_id)
                    if not custom_id:
                        st.error("❌ Impossible de créer le champ personnalisé vide.")
                        st.stop()

            with st.spinner("Préparation du mapping et envoi à BeezUP..."):
                # 2️⃣ Récupère le mapping actuel
                mapping_data = client.get_channel_catalog_data(catalog_id) or {}
                existing = mapping_data.get("columnMappings", [])

                # 3️⃣ Prépare le nouveau mapping complet
                new_payload = existing + [
                    {"channelColumnId": attr_id, "catalogColumnId": custom_id}
                    for attr_id in attrs_to_map
                ]

                # 4️⃣ Envoie la mise à jour
                resp = client.update_column_mapping(catalog_id, new_payload)
                if resp.status_code in (200, 204):
                    st.success(f"✅ {len(attrs_to_map)} attribut(s) ont été associés au champ personnalisé vide.")
                else:
                    st.error(f"❌ Erreur API ({resp.status_code}) : {resp.text}")


    






















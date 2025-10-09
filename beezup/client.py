import requests
import logging

class BeezUPClient:
    """
    Client pour interagir avec l'API BeezUP v2.
    Gère les méthodes GET, POST, PUT avec gestion d'erreur centralisée.
    Fournit des méthodes utilitaires pour chaque endpoint clé utilisé dans le projet.
    """

    BASE_URL = "https://api.beezup.com/v2"

    def __init__(self, api_key):
        self.headers = {
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate, br",
            "X-BeezUP-Decrypted-Expression": "true",
            "Ocp-Apim-Subscription-Key": api_key
        }

    def get(self, route, params=None):
        url = f"{self.BASE_URL}{route}"
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            logging.error(f"[BeezUPClient] Timeout lors de la requête GET : {url}")
        except requests.exceptions.ConnectionError:
            logging.error(f"[BeezUPClient] Erreur de connexion lors de la requête GET : {url}")
        except requests.exceptions.HTTPError:
            logging.error(f"[BeezUPClient] Erreur HTTP {resp.status_code} pour l'URL {url} : {resp.text}")
        except Exception as e:
            logging.error(f"[BeezUPClient] Erreur inattendue lors de la requête GET : {e}")
        return None

    def post(self, route, data=None):
        url = f"{self.BASE_URL}{route}"
        try:
            resp = requests.post(url, headers=self.headers, json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            logging.error(f"[BeezUPClient] Timeout lors de la requête POST : {url}")
        except requests.exceptions.ConnectionError:
            logging.error(f"[BeezUPClient] Erreur de connexion lors de la requête POST : {url}")
        except requests.exceptions.HTTPError:
            logging.error(f"[BeezUPClient] Erreur HTTP {resp.status_code} pour l'URL {url} : {resp.text}")
        except Exception as e:
            logging.error(f"[BeezUPClient] Erreur inattendue lors de la requête POST : {e}")
        return None

    def put(self, route, data=None):
        url = f"{self.BASE_URL}{route}"
        try:
            resp = requests.put(url, headers=self.headers, json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            logging.error(f"[BeezUPClient] Timeout lors de la requête PUT : {url}")
        except requests.exceptions.ConnectionError:
            logging.error(f"[BeezUPClient] Erreur de connexion lors de la requête PUT : {url}")
        except requests.exceptions.HTTPError:
            logging.error(f"[BeezUPClient] Erreur HTTP {resp.status_code} pour l'URL {url} : {resp.text}")
        except Exception as e:
            logging.error(f"[BeezUPClient] Erreur inattendue lors de la requête PUT : {e}")
        return None

    # --- Endpoints spécifiques BeezUP --- #

    def get_channel_catalog_data(self, catalog_id):
        """Récupère les infos du channelCatalog (storeId, channelId, etc.)."""
        return self.get(f"/user/channelCatalogs/{catalog_id}")

    def get_catalog_columns(self, store_id):
        """Récupère la liste des colonnes du catalogue vendeur."""
        return self.get(f"/user/catalogs/{store_id}/catalogColumns")

    def get_products(self, catalog_id, payload):
        """Récupère les produits (canal de vente) à partir d'une liste d'EANs."""
        return self.post(f"/user/channelCatalogs/{catalog_id}/products", data=payload)

    def get_product_values(self, store_id, payload):
        """Récupère les valeurs de champs catalogue via products/list (productIdList ou eanList)."""
        return self.post(f"/user/catalogs/{store_id}/products/list", data=payload)

    def get_category_mapping_data(self, catalog_id):
        """Récupère le mapping des catégories canal de vente ↔ catalogue Octopia."""
        return self.get(f"/user/channelCatalogs/{catalog_id}/categories")

    def get_channel_attributes_data(self, catalog_id):
        """Récupère la liste des attributs canal de vente (par catégorie)."""
        return self.get(f"/user/channelCatalogs/{catalog_id}/attributes")

    def get_attribute_value_list(self, catalog_id, attribute_id):
        """Récupère les valeurs autorisées (listes) pour un attribut donné."""
        return self.get(f"/user/channelCatalogs/{catalog_id}/attributes/{attribute_id}/mapping")

    # --- Gestion du mapping et des colonnes personnalisées --- #

    def get_custom_columns(self, store_id):
        """Récupère la liste des colonnes personnalisées du catalogue vendeur."""
        return self.get(f"/user/catalogs/{store_id}/customColumns")

    def create_custom_column(self, store_id, name="Champ perso vide généré par API"):
        """Crée une colonne personnalisée vide (renvoie son ID si succès)."""
        import uuid
        column_id = str(uuid.uuid4())
        route = f"/user/catalogs/{store_id}/customColumns/{column_id}/decrypted"

        body = {
            "displayGroupName": "Personnalised Fields",
            "blocklyExpression": "<block xmlns=\"http://www.w3.org/1999/xhtml\" type=\"beezup_start\" deletable=\"false\"> <value name=\"startValue\"><block type=\"text\"><field name=\"TEXT\"></field></block></value></block>",
            "expression": "\"\"",
            "userColumnName": name,
        }

        resp = requests.put(f"{self.BASE_URL}{route}", headers=self.headers, json=body)
        if resp.status_code == 204:
            return column_id
        else:
            import logging
            logging.error(f"[BeezUPClient] Erreur création custom column ({resp.status_code}): {resp.text}")
            return None

    def update_column_mapping(self, catalog_id, payload):
        """Met à jour le mapping complet (columnMappings) pour le channelCatalog."""
        route = f"/user/channelCatalogs/{catalog_id}/columnMappings"
        resp = requests.put(f"{self.BASE_URL}{route}", headers=self.headers, json=payload)
        if resp.status_code not in (200, 204):
            import logging
            logging.error(f"[BeezUPClient] Erreur mapping ({resp.status_code}): {resp.text}")
        return resp





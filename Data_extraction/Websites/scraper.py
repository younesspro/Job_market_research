import asyncio
import os
import json
from crawl4ai import AsyncWebCrawler
from groq import Groq
from jsonschema import validate, ValidationError

# --- Configuration ---
os.environ["GROQ_API_KEY"] = "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"
client = Groq(api_key=os.environ["GROQ_API_KEY"])

# URL de base (sans paramètre de page)
BASE_URL = "https://www.rekrute.com/offres.html?st=d&keywordNew=1&jobLocation=RK&tagSearchKey=&keyword=data"
BASE_URL = BASE_URL.strip()

# Schéma JSON pour validation
JOB_SCHEMA = {
    "type": "object",
    "properties": {
        "job_url": {"type": "string"},
        "titre": {"type": "string"},
        "companie": {"type": "string"},
        "description": {"type": "string"},
        "niveau_etudes": {"type": "string"},
        "niveau_experience": {"type": ["string", "null"]},
        "contrat": {"type": "string"},
        "region": {"type": "string"},
        "competences": {"type": "string"},
        "secteur": {"type": "string"},
        "salaire": {"type": ["integer", "string"]},
        "domaine": {"type": "string"},
        "extra": {"type": "string"},
        "via": {"type": "string"},
        "publication_date": {"type": "string", "format": "date"}
    },
    "required": ["job_url", "titre", "via", "publication_date"]
}


# Vérifier l'existence du fichier et charger le schéma JSON
#if not os.path.exists(SCHEMA_PATH):
 #   print(f"[❌] Fichier {SCHEMA_PATH} introuvable. Vérifiez le chemin ou utilisez un chemin absolu : D:\\Job_market_research-main\\Data_extraction\\Websites\\job_schema.json")
  #  exit(1)

#try:
 #   with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
  #      JOB_SCHEMA = json.load(f)
   # print("[✅] Schéma JSON chargé avec succès depuis", SCHEMA_PATH)
#except json.JSONDecodeError as e:
 #   print(f"[❌] Erreur lors du décodage du fichier JSON {SCHEMA_PATH} : {e}")
  #  exit(1)


# Prompt pour Groq
PROMPT = """
Tu es un extracteur spécialisé en offres d'emploi.

À partir de cette page Rekrute.com, extrait toutes les offres disponibles sous forme de tableau JSON avec la clé "offres". Chaque offre doit contenir les champs suivants :
- job_url (URL de l'offre, obligatoire)
- titre (titre de l'offre, obligatoire)
- companie (nom de l'entreprise)
- description (description de l'offre)
- niveau_etudes (niveau d'études requis)
- niveau_experience (niveau d'expérience requis, peut être null)
- contrat (type de contrat)
- region (région géographique)
- competences (compétences clés)
- secteur (secteur d'activité)
- salaire (salaire, peut être un entier ou une chaîne)
- domaine (domaine de l'offre)
- extra (informations supplémentaires)
- via (source de l'offre, par exemple "Rekrute", obligatoire)
- publication_date (date de publication au format YYYY-MM-DD, obligatoire)

Si une information n'est pas trouvée, utilise "N/A" sauf pour les champs obligatoires (job_url, titre, via, publication_date), qui doivent être présents. Format de sortie : uniquement un tableau JSON valide avec la clé "offres", sans texte supplémentaire.
"""

async def scrape_and_extract_with_groq():
    all_offers = []
    page = 1

    while True:
        # Construire l'URL paginée
        paginated_url = f"{BASE_URL}&page={page}"
        print(f"[INFO] Scraping de la page {page} : {paginated_url}")

        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(
                url=paginated_url,
                js_code="""
                const selectors = ['.offer', '.job-item', '[class*="job"]', '[class*="offer"]'];
                let offers = [];
                let attempt = 0;

                const waitForJobs = () => {
                    return new Promise((resolve) => {
                        const check = () => {
                            for (let selector of selectors) {
                                offers = document.querySelectorAll(selector);
                                if (offers.length > 0) {
                                    let offerHtml = '';
                                    offers.forEach(offer => {
                                        offerHtml += offer.outerHTML + '\n';
                                    });
                                    document.body.innerHTML = offerHtml;
                                    resolve('Offres trouvées avec ' + selector);
                                    return;
                                }
                            }
                            if (attempt < 20) {
                                attempt++;
                                setTimeout(check, 1000);
                            } else {
                                resolve(false);
                            }
                        };
                        check();
                    });
                };
                return waitForJobs();
                """
            )

            if not result.success:
                print(f"[❌] Échec lors du chargement de la page {page}.")
                break

            print("[✅] Page chargée avec succès.")
            print("[DEBUG] Longueur du HTML nettoyé :", len(result.cleaned_html))

            # Vérifier si la page est vide ou indique la fin
            if len(result.cleaned_html) < 1000 or "aucune offre" in result.cleaned_html.lower():
                print(f"[INFO] Fin des pages détectée à la page {page}.")
                break

            # Diviser le HTML en chunks pour respecter la limite de tokens
            chunk_size = 5000
            html_chunks = [result.cleaned_html[i:i + chunk_size] for i in range(0, len(result.cleaned_html), chunk_size)]
            print(f"[INFO] Nombre de chunks créés pour la page {page} : {len(html_chunks)}")

            # Extraire les données de chaque chunk
            page_offers = []
            for chunk_idx, chunk in enumerate(html_chunks):
                print(f"[INFO] Traitement du chunk {chunk_idx + 1}/{len(html_chunks)} (longueur : {len(chunk)} caractères)")
                try:
                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": "Vous êtes un assistant spécialisé dans l'extraction structurée d'informations."},
                            {"role": "user", "content": f"{PROMPT}\n\nVoici le HTML de la page emploi :\n\n{chunk}"}
                        ]
                    )
                    chunk_data = json.loads(completion.choices[0].message.content)
                    if "offres" in chunk_data:
                        page_offers.extend(chunk_data["offres"])
                    else:
                        print(f"[⚠️] Aucun 'offres' trouvé dans le chunk {chunk_idx + 1}")
                except Groq.APIStatusError as e:
                    print(f"[❌] Erreur API Groq pour le chunk {chunk_idx + 1} : {e}")
                    continue
                except Exception as e:
                    print(f"[❌] Erreur inattendue pour le chunk {chunk_idx + 1} : {e}")
                    continue

                if chunk_idx < len(html_chunks) - 1:
                    print("[INFO] Pause de 5 secondes pour éviter la limite de tokens...")
                    await asyncio.sleep(5)

            all_offers.extend(page_offers)
            page += 1

        if not page_offers:
            print(f"[INFO] Aucune offre trouvée sur la page {page}, arrêt de la pagination.")
            break

    if not all_offers:
        print("[❌] Aucune donnée extraite après traitement de toutes les pages.")
        return None

    extracted_data = json.dumps({"offres": all_offers})
    print("[DEBUG] Données extraites brutes :", extracted_data)
    return extracted_data

async def main():
    print("[🔍] Démarrage du scraping et extraction IA...\n")
    extracted_content = await scrape_and_extract_with_groq()

    if not extracted_content:
        print("\n❌ Aucune donnée extraite.")
        return

    try:
        data = json.loads(extracted_content)
        if "offres" not in data:
            print("\n❌ Les données extraites ne contiennent pas la clé 'offres'.")
            return
        offers = data["offres"]
    except json.JSONDecodeError as e:
        print(f"\n❌ Erreur lors du décodage JSON : {e}")
        return

    valid_offers = []
    for i, offer in enumerate(offers):
        try:
            validate(instance=offer, schema=JOB_SCHEMA)
            valid_offers.append(offer)
            print(f"[✅] Offre {i + 1} validée avec succès.")
        except ValidationError as e:
            print(f"[⚠️] Offre {i + 1} non valide : {e.message}")

    if valid_offers:
        final_data = {"offres": valid_offers}
        print("\n🧠 Données validées :")
        print(json.dumps(final_data, indent=2))

        with open("offres_emploi_groq.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)

        print("\n💾 Données sauvegardées dans 'offres_emploi_groq.json'")
    else:
        print("\n❌ Aucune offre valide à sauvegarder.")

if __name__ == "__main__":
    asyncio.run(main())
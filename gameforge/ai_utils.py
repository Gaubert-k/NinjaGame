import random
import os
import json
import re
import io


import requests
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from huggingface_hub import InferenceClient
import logging
try:
    from .models import AISettings
except ImportError:
    AISettings = None

try:
    from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer
    import torch

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)

MODEL_LOADED = False
text_generator = None
tokenizer = None
USE_REMOTE_LLM = False
REMOTE_LLM_URL = None


def clean_llm_output(text):
    """
    Nettoie le texte généré par le LLM en supprimant les balises parasites,
    les consignes internes et autres éléments non destinés à l'utilisateur.

    Args:
        text (str): Texte brut généré par le LLM

    Returns:
        str: Texte nettoyé
    """
    # Supprimer les balises <think>...</think> et leur contenu
    cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    # Supprimer les consignes système courantes (ajouter d'autres motifs au besoin)
    patterns_to_remove = [
        r'CONSIGNE DE REPONSE\s*:.*?(?=\n\n|\Z)',
        r'AUCUN SMILEY, AUCUN TEXTE GRAS.*?(?=\n\n|\Z)',
        r'JE VEUX UN TEXTE PLAT.*?(?=\n\n|\Z)',
        r'#\d+',  # Supprime les identifiants comme #27015
        r'\d+\s*(?=#\d+)',  # Supprime les nombres avant les identifiants
    ]

    for pattern in patterns_to_remove:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.DOTALL | re.IGNORECASE)

    # Supprimer les lignes commençant par des chiffres suivis d'un espace (comme "16 ", "17 ")
    cleaned_text = re.sub(r'^\d+\s+', '', cleaned_text, flags=re.MULTILINE)

    # Supprimer le formatage Markdown
    # Supprimer les ** pour le texte en gras
    cleaned_text = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned_text)
    # Supprimer les * pour le texte en italique
    cleaned_text = re.sub(r'\*(.*?)\*', r'\1', cleaned_text)
    # Supprimer les ` pour le code
    cleaned_text = re.sub(r'`(.*?)`', r'\1', cleaned_text)
    # Supprimer les # pour les titres
    cleaned_text = re.sub(r'^#{1,6}\s+', '', cleaned_text, flags=re.MULTILINE)
    # Supprimer les liens markdown [texte](url)
    cleaned_text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', cleaned_text)

    # Nettoyer les doubles espaces et lignes vides multiples
    cleaned_text = re.sub(r'\s{2,}', ' ', cleaned_text)
    cleaned_text = re.sub(r'\n\s*\n', '\n\n', cleaned_text)

    # Supprimer les tirets d'énumération isolés
    cleaned_text = re.sub(r'^\s*-\s*$', '', cleaned_text, flags=re.MULTILINE)

    # Nettoyer le début et la fin du texte
    cleaned_text = cleaned_text.strip()

    return cleaned_text

def get_ai_settings():
    global USE_REMOTE_LLM, REMOTE_LLM_URL


    if AISettings is not None:
        try:
            ai_settings = AISettings.get_settings()
            USE_REMOTE_LLM = ai_settings.use_remote_llm
            REMOTE_LLM_URL = ai_settings.remote_llm_url
            return
        except Exception as e:
            logger.error(f"Error getting AI settings from database: {e}")

    USE_REMOTE_LLM = settings.USE_REMOTE_LLM
    REMOTE_LLM_URL = settings.REMOTE_LLM_URL

get_ai_settings()

if TRANSFORMERS_AVAILABLE and not USE_REMOTE_LLM:
    try:
        model_name = "LaiCharts/OsGPT"

        logger.info(f"Début du chargement du modèle {model_name}...")

        # Chargement du tokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        logger.info(f"Tokenizer {model_name} chargé")

        # Chargement du modèle avec optimisations CPU uniquement
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            low_cpu_mem_usage=True,  # Économiser la mémoire
            torch_dtype=torch.float32,  # Format 32-bit standard pour CPU
        )
        logger.info(f"Modèle {model_name} chargé")

        # Créer le pipeline avec le modèle optimisé pour CPU
        text_generator = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            device=-1,  # Forcer l'utilisation du CPU
            batch_size=1  # Ne pas surcharger la mémoire
        )

        # Test simple du modèle
        test_result = text_generator("Bonjour, je suis un", max_length=30, do_sample=True, temperature=1.0)
        logger.info(f"Test du modèle: {test_result[0]['generated_text']}")

        MODEL_LOADED = True
        logger.info(f"Modèle {model_name} initialisé avec succès")
    except Exception as e:
        logger.error(f"Erreur lors du chargement du modèle: {e}")
        logger.error(f"Détail: {str(e)}")
        logger.info("Utilisation du mode de génération aléatoire comme solution de repli")
elif USE_REMOTE_LLM:
    try:
        logger.info(f"Utilisation du LLM distant à {REMOTE_LLM_URL}")
        response = requests.get(f"{REMOTE_LLM_URL}/health", timeout=5)
        if response.status_code == 200:
            MODEL_LOADED = True
            logger.info("LLM distant disponible et prêt à être utilisé")
        else:
            logger.error(f"LLM distant non disponible: {response.status_code}")
            logger.info("Utilisation du mode de génération aléatoire comme solution de repli")
    except Exception as e:
        logger.error(f"Erreur lors de la connexion au LLM distant: {e}")
        logger.info("Utilisation du mode de génération aléatoire comme solution de repli")

# Listes existantes conservées comme solution de repli (inchangées)
GAME_TITLES = [
    "Echoes of Eternity", "Crimson Horizon", "Nebula Nexus", "Forgotten Realms",
    "Shadow's Edge", "Crystal Chronicles", "Astral Odyssey", "Mystic Legends",
    "Quantum Quest", "Celestial Siege", "Void Voyagers", "Arcane Ascendancy"
]

CHARACTER_NAMES = [
    "Aria", "Thorne", "Zephyr", "Luna", "Orion", "Nova", "Caspian", "Seraphina",
    "Atlas", "Lyra", "Phoenix", "Ember", "Sage", "Raven", "Cyrus", "Elara"
]

CHARACTER_CLASSES = [
    "Warrior", "Mage", "Rogue", "Cleric", "Paladin", "Ranger", "Druid", "Bard",
    "Necromancer", "Monk", "Sorcerer", "Alchemist", "Summoner", "Assassin"
]

CHARACTER_ROLES = [
    "Protagonist", "Antagonist", "Mentor", "Ally", "Rival", "Guardian", "Trickster",
    "Sidekick", "Anti-hero", "Villain", "Love Interest", "Sage"
]

LOCATION_NAMES = [
    "The Whispering Woods", "Crystal Caverns", "Forgotten Citadel", "Misty Mountains",
    "Sunken Temple", "Celestial Sanctum", "Neon Metropolis", "Ancient Ruins",
    "Ethereal Plains", "Volcanic Forge", "Frozen Tundra", "Enchanted Garden"
]


def generate_text(prompt, max_length=150, max_new_tokens=80, patience=2):
    """
    Génère du texte en utilisant soit le modèle local de transformers soit un LLM distant.

    Args:
        prompt (str): Texte de prompt pour amorcer la génération
        max_length (int, optional): Longueur maximale du texte généré
        max_new_tokens (int, optional): Nombre maximum de nouveaux tokens à générer
        patience (int, optional): Niveau de patience (1-3) influençant les paramètres de génération

    Returns:
        str: Le texte généré
    """
    # Reload settings in case they've changed
    get_ai_settings()

    if not MODEL_LOADED:
        logger.warning(f"Modèle non chargé: {prompt}")
        return f"{prompt} (mode texte aléatoire)"

    # Ajuster les paramètres selon le niveau de patience
    if patience == 1:  # Rapide mais moins créatif
        temperature = 0.7
        top_p = 0.85
        repetition_penalty = 1.1
    elif patience == 3:  # Lent mais plus créatif
        temperature = 1.2
        top_p = 0.95
        repetition_penalty = 1.3
    else:  # Équilibré (par défaut)
        temperature = 0.9
        top_p = 0.9
        repetition_penalty = 1.2

    try:
        # Ajout d'un identifiant unique pour éviter les répétitions entre appels
        unique_id = random.randint(1, 10000)
        full_prompt = f"{prompt} #{unique_id}"

        if USE_REMOTE_LLM:
            # Utiliser le LLM distant
            payload = {
                "prompt": full_prompt,
                "max_tokens": 200,#"max_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "repetition_penalty": repetition_penalty,
                "stop": []
            }

            response = requests.post(
                f"{REMOTE_LLM_URL}/v1/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()

                print("DEBUG ------ > ")
                print(result)

                generated_text = result.get("choices", [{}])[0].get("text", "")

                # Nettoyer le texte généré
                clean_text = generated_text.strip()

                clean_text = clean_llm_output(clean_text)

                # Si la génération échoue à produire du contenu nouveau
                if not clean_text or len(clean_text) < 5:
                    logger.warning(f"Génération insuffisante pour: {prompt}")
                    # Essayer à nouveau avec des paramètres différents
                    return generate_text(prompt, max_length, max_new_tokens, patience=min(patience + 1, 3))

                return clean_text
            else:
                logger.error(f"Erreur API LLM distant: {response.status_code} - {response.text}")
                return f"{prompt} (erreur API: {response.status_code})"
        else:
            # Utiliser le modèle local
            result = text_generator(
                full_prompt,
                max_length=max_length,
                max_new_tokens=max_new_tokens,
                num_return_sequences=1,
                temperature=temperature,
                do_sample=True,
                top_p=top_p,
                top_k=50,
                repetition_penalty=repetition_penalty,
                no_repeat_ngram_size=3,
                pad_token_id=tokenizer.eos_token_id
            )

            # Extraire et nettoyer le texte généré
            generated_text = result[0]['generated_text']

            # Supprimer l'identifiant unique et le prompt original
            clean_text = generated_text.replace(full_prompt, "", 1).strip()

            # Appliquer le nettoyage des balises <think>
            clean_text = clean_llm_output(clean_text)

            # Si la génération échoue à produire du contenu nouveau
            if not clean_text or len(clean_text) < 5:
                logger.warning(f"Génération insuffisante pour: {prompt}")
                # Essayer à nouveau avec des paramètres différents
                return generate_text(prompt, max_length, max_new_tokens, patience=min(patience + 1, 3))

            return clean_text
    except Exception as e:
        logger.error(f"Erreur lors de la génération de texte: {e}")
        return f"{prompt} (erreur: {str(e)[:30]}...)"


def generate_story(title, genre, ambiance, keywords=None, refs= None, random_mode=False):
    """
    Génère une histoire pour un jeu basée sur le genre, l'ambiance et les mots-clés.

    Args:
        genre (str): Le genre du jeu
        ambiance (str): L'ambiance du jeu
        keywords (str, optional): Mots-clés séparés par des virgules
        random_mode (bool, optional): Générer du contenu complètement aléatoire

    Returns:
        dict: Un dictionnaire contenant les éléments de l'histoire
    """
    logger.info(f"Génération d'histoire: {genre}, {ambiance}, mode aléatoire: {random_mode}")

    if random_mode or not MODEL_LOADED:
        # Contenu aléatoire (inchangé)
        title = random.choice(GAME_TITLES)
        story = {
            "title": title,
            "premise": f"Dans un monde {ambiance.lower()}, un héros se lance dans une aventure {genre.lower()} pour sauver leur royaume d'un mal ancien.",
            "act1": f"Le héros découvre son destin et part de ses humbles origines, rassemblant des alliés et des ressources pour le voyage à venir.",
            "act2": f"Face à des défis de plus en plus difficiles, la détermination du héros est mise à l'épreuve. Ils découvrent des vérités cachées sur le monde et sur eux-mêmes.",
            "act3": f"Après avoir surmonté leurs démons intérieurs, le héros affronte le mal ultime dans un affrontement épique qui détermine le destin du monde.",
            "twist": f"Le mal ancien se révèle être une manifestation des propres peurs et doutes du héros, les forçant à affronter leur véritable moi."
        }
    else:
        # Construire des prompts détaillés pour de meilleurs résultats
        key_terms = f"{genre} {ambiance}"
        if keywords:
            key_terms += f" {keywords}"

        # Prompts en français pour de meilleurs résultats avec les modèles multilingues
        # title_prompt = f"Titre original d'un jeu vidéo {genre} avec ambiance {ambiance}:"
        base_context = f"""
        CONSIGNE DE REPONSE : AUCUN SMILEY, AUCUN TEXTE GRAS , AUCUNE MISE EN FORME, JE VEUX UN TEXTE PLAT
        Génération pour un jeu vidéo avec les caractéristiques suivantes:
        - Titre: {title}
        - Genre: {genre}
        - Ambiance: {ambiance}
        - Mots-clés: {keywords}
        - Inspirations/Références: {refs}
        """

        title_prompt = f"""
        {base_context}
        Propose un titre original, accrocheur et mémorable qui capture parfaitement l'essence de ce jeu.
        Le titre doit être court (2-5 mots maximum) et évocateur.
        """
        premise_prompt = f"""

        {base_context}
        Rédige un synopsis captivant pour ce jeu qui présente:
        - L'univers et son ambiance {ambiance}
        - Le concept central du gameplay
        - La situation initiale qui lance l'aventure
        - Ce qui rend ce jeu unique dans le genre {genre}
        (Entre 3 et 5 phrases maximum)
        """

        act1_prompt = f"""
        {base_context}
        Décris le premier acte du jeu qui doit inclure:
        - L'introduction du protagoniste et sa situation initiale
        - Les événements déclencheurs qui lancent l'aventure
        - Les premiers objectifs/missions du joueur
        - Les mécaniques de base introduites
        - L'ambiance {ambiance} mise en place
        (Entre 4 et 6 phrases)
        """

        act2_prompt = f"""
        {base_context}
        Décris le deuxième acte du jeu qui doit détailler:
        - L'évolution des enjeux et l'intensification du conflit principal
        - Les défis croissants auxquels le joueur fait face
        - Les nouvelles mécaniques/capacités débloquées
        - Les rebondissements qui complexifient l'histoire
        - Comment l'ambiance {ambiance} évolue
        (Entre 4 et 6 phrases)
        """

        act3_prompt = f"""
        {base_context}
        Décris le climax et la conclusion du jeu, incluant:
        - La confrontation finale ou défi ultime
        - Comment les mécaniques et l'histoire convergent
        - L'utilisation des capacités complètes du joueur
        - La résolution des principaux arcs narratifs
        - L'impact émotionnel final fidèle à l'ambiance {ambiance}
        (Entre 4 et 6 phrases)
        """

        twist_prompt = f"""
        {base_context}
        Propose un rebondissement narratif ou ludique inattendu qui:
        - Surprend le joueur à un moment clé de l'aventure
        - Transforme sa perception de l'histoire ou des mécaniques
        - Reste cohérent avec l'univers et le genre {genre}
        - Ajoute une profondeur supplémentaire à l'expérience
        (Entre 2 et 3 phrases percutantes)
        """

        # Générer le contenu avec patience variable
        story = {
            "title": generate_text(title_prompt, max_length=50, max_new_tokens=15, patience=1),
            "premise": generate_text(premise_prompt, max_length=150, max_new_tokens=80, patience=2),
            "act1": generate_text(act1_prompt, max_length=150, max_new_tokens=80, patience=2),
            "act2": generate_text(act2_prompt, max_length=150, max_new_tokens=80, patience=2),
            "act3": generate_text(act3_prompt, max_length=150, max_new_tokens=80, patience=2),
            "twist": generate_text(twist_prompt, max_length=150, max_new_tokens=80, patience=3)
        }

    return story


def generate_characters(game_genre, count=2):
    """
    Génère des personnages pour un jeu.

    Args:
        game_genre (str): Le genre du jeu
        count (int, optional): Nombre de personnages à générer

    Returns:
        list: Une liste de dictionnaires de personnages
    """
    characters = []

    # Fonctions pour générer des noms et classes aléatoires ou via modèle
    def get_name(role):
        if MODEL_LOADED:
            prompt = f"Un nom original pour un {role} dans un jeu {game_genre}:"
            name = generate_text(prompt, max_length=30, max_new_tokens=10, patience=1)
            # Extraire juste le premier mot significatif
            name_parts = name.split()
            if len(name_parts) > 0:
                for part in name_parts:
                    # Chercher un mot significatif de 3 caractères ou plus
                    if len(part) >= 3 and part[0].isupper():
                        return part
            return name_parts[0] if len(name_parts) > 0 else "Héros"
        return random.choice(CHARACTER_NAMES)

    def get_class(role):
        if MODEL_LOADED:
            prompt = f"Une classe typique pour un {role} dans un jeu {game_genre}:"
            class_text = generate_text(prompt, max_length=30, max_new_tokens=10, patience=1)
            # Extraire le premier mot pertinent
            words = class_text.split()
            for word in words:
                if len(word) >= 4 and word not in ["pour", "dans", "avec", "qui", "est", "une", "type"]:
                    return word.capitalize()
            return words[0].capitalize() if words else "Guerrier"
        return random.choice(CHARACTER_CLASSES)

    # Toujours inclure un protagoniste
    if MODEL_LOADED:
        background_prompt = f"Histoire et motivations d'un protagoniste héroïque dans un jeu {game_genre}:"
        gameplay_prompt = f"Les capacités et le style de jeu d'un protagoniste dans un jeu {game_genre}:"
        background = generate_text(background_prompt, max_length=150, max_new_tokens=80, patience=2)
        gameplay = generate_text(gameplay_prompt, max_length=150, max_new_tokens=80, patience=2)
    else:
        background = f"Un individu déterminé avec un passé mystérieux, cherchant à trouver sa place dans le monde."
        gameplay = f"Capacités équilibrées avec potentiel de croissance dans plusieurs directions basées sur les choix du joueur."

    characters.append({
        "name": get_name("protagoniste"),
        "character_class": get_class("protagoniste"),
        "role": "Protagonist",
        "background": background,
        "gameplay": gameplay
    })

    # Ajouter un antagoniste
    if MODEL_LOADED:
        background_prompt = f"Histoire et motivations d'un antagoniste mémorable dans un jeu {game_genre}:"
        gameplay_prompt = f"Les capacités et les tactiques d'un antagoniste dans un jeu {game_genre}:"
        background = generate_text(background_prompt, max_length=150, max_new_tokens=80, patience=2)
        gameplay = generate_text(gameplay_prompt, max_length=150, max_new_tokens=80, patience=2)
    else:
        background = f"Autrefois une figure respectée qui a été corrompue par le pouvoir et cherche maintenant à remodeler le monde selon sa vision."
        gameplay = f"Capacités puissantes qui défient le joueur, avec des mécaniques uniques qui doivent être comprises pour vaincre."

    characters.append({
        "name": get_name("antagoniste"),
        "character_class": get_class("antagoniste"),
        "role": "Antagonist",
        "background": background,
        "gameplay": gameplay
    })

    # Ajouter des personnages supplémentaires si demandé
    for i in range(count - 2):
        if i >= 0:  # Vérification pour éviter les indices négatifs si count < 2
            role = random.choice([r for r in CHARACTER_ROLES if r not in ["Protagonist", "Antagonist"]])

            if MODEL_LOADED:
                background_prompt = f"Histoire et motivations d'un personnage {role.lower()} dans un jeu {game_genre}:"
                gameplay_prompt = f"Les capacités et l'utilité d'un personnage {role.lower()} dans un jeu {game_genre}:"
                background = generate_text(background_prompt, max_length=150, max_new_tokens=80, patience=2)
                gameplay = generate_text(gameplay_prompt, max_length=150, max_new_tokens=80, patience=2)
            else:
                background = f"Un individu unique avec ses propres motivations et son histoire, dont le chemin croise celui du protagoniste."
                gameplay = f"Capacités spécialisées qui complètent l'équipe et fournissent des options stratégiques dans diverses situations."

            characters.append({
                "name": get_name(role.lower()),
                "character_class": get_class(role.lower()),
                "role": role,
                "background": background,
                "gameplay": gameplay
            })

    return characters


def generate_locations(game_ambiance, count=2):
    """
    Génère des lieux pour un jeu.

    Args:
        game_ambiance (str): L'ambiance du jeu
        count (int, optional): Nombre de lieux à générer

    Returns:
        list: Une liste de dictionnaires de lieux
    """
    locations = []

    for i in range(count):
        if MODEL_LOADED:
            name_prompt = f"Un nom évocateur pour un lieu avec ambiance {game_ambiance}:"
            name = generate_text(name_prompt, max_length=40, max_new_tokens=15, patience=1)

            desc_prompt = f"Description atmosphérique d'un lieu {game_ambiance} nommé {name}:"
            description = generate_text(desc_prompt, max_length=150, max_new_tokens=80, patience=2)
        else:
            name = random.choice(LOCATION_NAMES)
            description = f"Un lieu avec une ambiance {game_ambiance.lower()} avec des défis uniques et des secrets à découvrir. L'atmosphère ici reflète le ton général du monde tout en offrant des opportunités de gameplay distinctes."

        locations.append({
            "name": name,
            "description": description
        })

    return locations


def generate_placeholder_image(prompt, image_type, filename):
    """
    Génère une image en utilisant le modèle de Hugging Face.

    Args:
        prompt (str): Le prompt de génération d'image
        image_type (str): Type d'image (CHARACTER, LOCATION, CONCEPT)
        filename (str): Nom de fichier pour sauvegarder l'image

    Returns:
        str: Chemin vers l'image générée
    """
    print("GENERATION D'IMAGE PLACEHOLDER")
    try:
        # Vérifier si le token Hugging Face est disponible
        huggingface_token = os.environ.get("HUGGINGFACE_API_KEY")

        if huggingface_token:
            # Initialiser l'InferenceClient avec le token
            client = InferenceClient(
                provider="cerebras",
                api_key=huggingface_token,
            )

            # Adapter le prompt en fonction du type d'image
            if image_type == 'CHARACTER':
                enhanced_prompt = f"Character portrait, {prompt}, detailed, fantasy style"
            elif image_type == 'LOCATION':
                enhanced_prompt = f"Fantasy location, {prompt}, detailed landscape, atmospheric"
            else:  # CONCEPT
                enhanced_prompt = f"Game concept art, {prompt}, detailed illustration"

            # Génération d'image avec le client Hugging Face
            image_bytes = client.text_to_image(
                model="stabilityai/stable-diffusion-xl-base-1.0",
                prompt=enhanced_prompt,
                negative_prompt="low quality, blurry, distorted, deformed, bad anatomy, ugly",
                height=512,
                width=512,
            )

            # Créer le dossier de destination s'il n'existe pas
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'game_images'), exist_ok=True)

            # Sauvegarder l'image
            media_path = os.path.join(settings.MEDIA_ROOT, 'game_images', filename)
            with open(media_path, 'wb') as f:
                f.write(image_bytes)

            # Retourner le chemin relatif pour la base de données
            return os.path.join('game_images', filename)
        else:
            logger.warning("Token Hugging Face non disponible, utilisation de l'image placeholder")
            return generate_fallback_image(prompt, image_type, filename)

    except Exception as e:
        logger.error(f"Erreur lors de la génération de l'image: {e}")
        # Fallback à l'image placeholder en cas d'erreur
        return generate_fallback_image(prompt, image_type, filename)


def generate_fallback_image(prompt, image_type, filename):
    """
    Génère une image placeholder avec du texte en cas d'échec de l'API Hugging Face.

    Args:
        prompt (str): Le prompt de génération d'image
        image_type (str): Type d'image (CHARACTER, LOCATION, CONCEPT)
        filename (str): Nom de fichier pour sauvegarder l'image

    Returns:
        str: Chemin vers l'image générée
    """
    try:
        # Créer un arrière-plan coloré basé sur le type d'image
        if image_type == 'CHARACTER':
            bg_color = (100, 100, 200)  # Bleu pour les personnages
        elif image_type == 'LOCATION':
            bg_color = (100, 200, 100)  # Vert pour les lieux
        else:
            bg_color = (200, 100, 100)  # Rouge pour les concepts

        # Créer une image simple avec du texte
        img = Image.new('RGB', (800, 600), color=bg_color)
        d = ImageDraw.Draw(img)

        # Essayer d'utiliser une police système
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            font = ImageFont.load_default()

        # Ajouter le texte du prompt
        d.text((50, 50), f"Type d'image: {image_type}", fill=(255, 255, 255), font=font)

        # Découper le texte du prompt
        words = prompt.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + word + " "
            if d.textlength(test_line, font=font) < 700:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word + " "
        lines.append(current_line)

        # Dessiner le texte découpé
        y_position = 100
        for line in lines:
            d.text((50, y_position), line, fill=(255, 255, 255), font=font)
            y_position += 30

        # Ajouter une note indiquant qu'il s'agit d'une image placeholder
        d.text((50, 500), "Ceci est une image placeholder. Ajoutez HUGGINGFACE_TOKEN", fill=(255, 255, 255),
               font=font)
        d.text((50, 530), "dans le fichier .ENV pour générer des images avec l'IA.", fill=(255, 255, 255), font=font)

        # Créer le dossier de destination s'il n'existe pas
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'game_images'), exist_ok=True)

        # Sauvegarder l'image
        media_path = os.path.join(settings.MEDIA_ROOT, 'game_images', filename)
        img.save(media_path)

        # Retourner le chemin relatif pour la base de données
        return os.path.join('game_images', filename)

    except Exception as e:
        logger.error(f"Erreur lors de la génération de l'image placeholder: {e}")
        # Retourner un chemin d'image par défaut en cas d'erreur
        return 'game_images/placeholder.jpg'


def check_model_status():
    """
    Fonction de diagnostic pour vérifier l'état du modèle.

    Returns:
        dict: Un dictionnaire contenant des informations sur l'état du modèle
    """
    # Reload settings in case they've changed
    get_ai_settings()

    status = {
        "transformers_available": TRANSFORMERS_AVAILABLE,
        "model_loaded": MODEL_LOADED,
        "use_remote_llm": USE_REMOTE_LLM,
        "tokenizer_loaded": tokenizer is not None if not USE_REMOTE_LLM else None
    }

    if USE_REMOTE_LLM:
        status["remote_llm_url"] = REMOTE_LLM_URL
        status["model_name"] = "qwen3-8b (remote)"
    else:
        status["model_name"] = "LaiCharts/OsGPT" if MODEL_LOADED else None

    # Essayer de générer du texte test si le modèle est chargé
    if MODEL_LOADED:
        try:
            test_prompt = "Test de génération:"
            test_result = generate_text(test_prompt, max_length=20, max_new_tokens=10)
            status["test_generation"] = test_result
            status["test_success"] = True
        except Exception as e:
            status["test_error"] = str(e)
            status["test_success"] = False

    return status

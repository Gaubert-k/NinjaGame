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
import openai
try:
    from .models import AISettings, UserAISettings
except ImportError:
    AISettings = None
    UserAISettings = None

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

def get_ai_settings(user=None):
    global USE_REMOTE_LLM, REMOTE_LLM_URL

    # If user is provided and has AI settings, use those
    if user and user.is_authenticated and UserAISettings is not None:
        try:
            user_settings, created = UserAISettings.objects.get_or_create(user=user)

            # Determine if we should use a remote LLM based on the user's AI service choice
            if user_settings.ai_service != 'LOCAL':
                USE_REMOTE_LLM = True

                # Set the appropriate URL based on the service
                if user_settings.ai_service == 'LMSTUDIO' and user_settings.lmstudio_url:
                    REMOTE_LLM_URL = user_settings.lmstudio_url
                elif user_settings.ai_service == 'HUGGINGFACE':
                    # For Hugging Face, we'll use the token directly in the API calls
                    # but we still need to set USE_REMOTE_LLM
                    REMOTE_LLM_URL = None
                elif user_settings.ai_service == 'CHATGPT':
                    # For ChatGPT, we'll use the OpenAI API directly
                    # but we still need to set USE_REMOTE_LLM
                    REMOTE_LLM_URL = None
                else:
                    # Fallback to default remote URL
                    REMOTE_LLM_URL = settings.REMOTE_LLM_URL
            else:
                # Use local LLM
                USE_REMOTE_LLM = False
                REMOTE_LLM_URL = None

            return user_settings
        except Exception as e:
            logger.error(f"Error getting user AI settings: {e}")

    # Fallback to global settings if no user or error occurred
    if AISettings is not None:
        try:
            ai_settings = AISettings.get_settings()
            USE_REMOTE_LLM = ai_settings.use_remote_llm
            REMOTE_LLM_URL = ai_settings.remote_llm_url
            return ai_settings
        except Exception as e:
            logger.error(f"Error getting AI settings from database: {e}")

    # Final fallback to settings.py
    USE_REMOTE_LLM = settings.USE_REMOTE_LLM
    REMOTE_LLM_URL = settings.REMOTE_LLM_URL
    return None

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


def generate_text(prompt, max_length=150, max_new_tokens=80, patience=2, user=None):
    """
    Génère du texte en utilisant le service d'IA préféré de l'utilisateur.

    Args:
        prompt (str): Texte de prompt pour amorcer la génération
        max_length (int, optional): Longueur maximale du texte généré
        max_new_tokens (int, optional): Nombre maximum de nouveaux tokens à générer
        patience (int, optional): Niveau de patience (1-3) influençant les paramètres de génération
        user (User, optional): L'utilisateur pour lequel générer du texte

    Returns:
        str: Le texte généré
    """
    # Reload settings in case they've changed
    user_settings = get_ai_settings(user)

    # Check if we have a valid model or user settings
    if not MODEL_LOADED and (user_settings is None or not isinstance(user_settings, UserAISettings)):
        logger.warning(f"Aucun modèle disponible pour: {prompt}")
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

        # Check if we're using a user-specific AI service
        if user and user.is_authenticated and isinstance(user_settings, UserAISettings):
            ai_service = user_settings.ai_service

            # Handle different AI services
            if ai_service == 'CHATGPT' and user_settings.chatgpt_token:
                # Use ChatGPT API
                openai.api_key = user_settings.chatgpt_token

                try:
                    response = openai.Completion.create(
                        model="gpt-3.5-turbo-instruct",
                        prompt=full_prompt,
                        max_tokens=max_new_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        frequency_penalty=repetition_penalty - 1.0,  # Convert to OpenAI scale
                        presence_penalty=0.0
                    )

                    generated_text = response.choices[0].text
                    clean_text = clean_llm_output(generated_text.strip())

                    if not clean_text or len(clean_text) < 5:
                        logger.warning(f"Génération ChatGPT insuffisante pour: {prompt}")
                        return generate_text(prompt, max_length, max_new_tokens, 
                                           patience=min(patience + 1, 3), user=user)

                    return clean_text
                except Exception as e:
                    logger.error(f"Erreur ChatGPT: {e}")
                    return f"{prompt} (erreur ChatGPT: {str(e)[:30]}...)"

            elif ai_service == 'HUGGINGFACE' and user_settings.huggingface_token:
                # Use Hugging Face API
                try:
                    client = InferenceClient(token=user_settings.huggingface_token)

                    response = client.text_generation(
                        prompt=full_prompt,
                        model="mistralai/Mistral-7B-Instruct-v0.2",
                        max_new_tokens=max_new_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        repetition_penalty=repetition_penalty
                    )

                    # Clean the response
                    clean_text = clean_llm_output(response.strip())

                    if not clean_text or len(clean_text) < 5:
                        logger.warning(f"Génération Hugging Face insuffisante pour: {prompt}")
                        return generate_text(prompt, max_length, max_new_tokens, 
                                           patience=min(patience + 1, 3), user=user)

                    return clean_text
                except Exception as e:
                    logger.error(f"Erreur Hugging Face: {e}")
                    return f"{prompt} (erreur Hugging Face: {str(e)[:30]}...)"

            elif ai_service == 'LMSTUDIO' and user_settings.lmstudio_url:
                # Use LM Studio API
                lmstudio_url = user_settings.lmstudio_url

                payload = {
                    "prompt": full_prompt,
                    "max_tokens": max_new_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                    "repetition_penalty": repetition_penalty,
                    "stop": []
                }

                try:
                    response = requests.post(
                        f"{lmstudio_url}/v1/completions",
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=30
                    )

                    if response.status_code == 200:
                        result = response.json()
                        generated_text = result.get("choices", [{}])[0].get("text", "")
                        clean_text = clean_llm_output(generated_text.strip())

                        if not clean_text or len(clean_text) < 5:
                            logger.warning(f"Génération LM Studio insuffisante pour: {prompt}")
                            return generate_text(prompt, max_length, max_new_tokens, 
                                               patience=min(patience + 1, 3), user=user)

                        return clean_text
                    else:
                        logger.error(f"Erreur API LM Studio: {response.status_code} - {response.text}")
                        return f"{prompt} (erreur API LM Studio: {response.status_code})"
                except Exception as e:
                    logger.error(f"Erreur de connexion à LM Studio: {e}")
                    return f"{prompt} (erreur de connexion à LM Studio: {str(e)[:30]}...)"

        # Fallback to standard remote or local LLM
        if USE_REMOTE_LLM and REMOTE_LLM_URL:
            # Utiliser le LLM distant
            payload = {
                "prompt": full_prompt,
                "max_tokens": 200,  # "max_tokens": max_new_tokens,
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
                generated_text = result.get("choices", [{}])[0].get("text", "")
                clean_text = clean_llm_output(generated_text.strip())

                if not clean_text or len(clean_text) < 5:
                    logger.warning(f"Génération insuffisante pour: {prompt}")
                    return generate_text(prompt, max_length, max_new_tokens, 
                                       patience=min(patience + 1, 3), user=user)

                return clean_text
            else:
                logger.error(f"Erreur API LLM distant: {response.status_code} - {response.text}")
                return f"{prompt} (erreur API: {response.status_code})"
        elif TRANSFORMERS_AVAILABLE and text_generator is not None:
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
            clean_text = generated_text.replace(full_prompt, "", 1).strip()
            clean_text = clean_llm_output(clean_text)

            if not clean_text or len(clean_text) < 5:
                logger.warning(f"Génération insuffisante pour: {prompt}")
                return generate_text(prompt, max_length, max_new_tokens, 
                                   patience=min(patience + 1, 3), user=user)

            return clean_text
        else:
            # No valid model available
            logger.warning(f"Aucun modèle disponible pour: {prompt}")
            return f"{prompt} (mode texte aléatoire)"
    except Exception as e:
        logger.error(f"Erreur lors de la génération de texte: {e}")
        return f"{prompt} (erreur: {str(e)[:30]}...)"


def generate_story(title, genre, ambiance, keywords=None, refs=None, random_mode=False, user=None):
    """
    Génère une histoire pour un jeu basée sur le genre, l'ambiance et les mots-clés.

    Args:
        title (str): Le titre du jeu
        genre (str): Le genre du jeu
        ambiance (str): L'ambiance du jeu
        keywords (str, optional): Mots-clés séparés par des virgules
        refs (str, optional): Références séparées par des virgules
        random_mode (bool, optional): Générer du contenu complètement aléatoire
        user (User, optional): L'utilisateur pour lequel générer l'histoire

    Returns:
        dict: Un dictionnaire contenant les éléments de l'histoire
    """
    logger.info(f"Génération d'histoire: {genre}, {ambiance}, mode aléatoire: {random_mode}")

    # Get user settings
    user_settings = get_ai_settings(user)

    # Check if we should use random mode
    use_random = random_mode

    # If user has no valid AI settings, use random mode
    if user and user.is_authenticated and isinstance(user_settings, UserAISettings):
        if user_settings.ai_service == 'LOCAL' and not MODEL_LOADED:
            use_random = True
        elif user_settings.ai_service == 'HUGGINGFACE' and not user_settings.huggingface_token:
            use_random = True
        elif user_settings.ai_service == 'CHATGPT' and not user_settings.chatgpt_token:
            use_random = True
        elif user_settings.ai_service == 'LMSTUDIO' and not user_settings.lmstudio_url:
            use_random = True
    elif not MODEL_LOADED:
        use_random = True

    if use_random:
        # Contenu aléatoire (inchangé)
        random_title = random.choice(GAME_TITLES)
        story = {
            "title": random_title,
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
            "title": generate_text(title_prompt, max_length=50, max_new_tokens=15, patience=1, user=user),
            "premise": generate_text(premise_prompt, max_length=150, max_new_tokens=80, patience=2, user=user),
            "act1": generate_text(act1_prompt, max_length=150, max_new_tokens=80, patience=2, user=user),
            "act2": generate_text(act2_prompt, max_length=150, max_new_tokens=80, patience=2, user=user),
            "act3": generate_text(act3_prompt, max_length=150, max_new_tokens=80, patience=2, user=user),
            "twist": generate_text(twist_prompt, max_length=150, max_new_tokens=80, patience=3, user=user)
        }

    return story


def generate_characters(game_genre, count=2, user=None):
    """
    Génère des personnages pour un jeu.

    Args:
        game_genre (str): Le genre du jeu
        count (int, optional): Nombre de personnages à générer
        user (User, optional): L'utilisateur pour lequel générer les personnages

    Returns:
        list: Une liste de dictionnaires de personnages
    """
    characters = []

    # Get user settings
    user_settings = get_ai_settings(user)

    # Check if we should use AI generation
    use_ai = True

    # If user has no valid AI settings, use random mode
    if user and user.is_authenticated and isinstance(user_settings, UserAISettings):
        if user_settings.ai_service == 'LOCAL' and not MODEL_LOADED:
            use_ai = False
        elif user_settings.ai_service == 'HUGGINGFACE' and not user_settings.huggingface_token:
            use_ai = False
        elif user_settings.ai_service == 'CHATGPT' and not user_settings.chatgpt_token:
            use_ai = False
        elif user_settings.ai_service == 'LMSTUDIO' and not user_settings.lmstudio_url:
            use_ai = False
    elif not MODEL_LOADED:
        use_ai = False

    # Fonctions pour générer des noms et classes aléatoires ou via modèle
    def get_name(role):
        if use_ai:
            prompt = f"Un nom original pour un {role} dans un jeu {game_genre}:"
            name = generate_text(prompt, max_length=30, max_new_tokens=10, patience=1, user=user)
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
        if use_ai:
            prompt = f"Une classe typique pour un {role} dans un jeu {game_genre}:"
            class_text = generate_text(prompt, max_length=30, max_new_tokens=10, patience=1, user=user)
            # Extraire le premier mot pertinent
            words = class_text.split()
            for word in words:
                if len(word) >= 4 and word not in ["pour", "dans", "avec", "qui", "est", "une", "type"]:
                    return word.capitalize()
            return words[0].capitalize() if words else "Guerrier"
        return random.choice(CHARACTER_CLASSES)

    # Toujours inclure un protagoniste
    if use_ai:
        background_prompt = f"Histoire et motivations d'un protagoniste héroïque dans un jeu {game_genre}:"
        gameplay_prompt = f"Les capacités et le style de jeu d'un protagoniste dans un jeu {game_genre}:"
        background = generate_text(background_prompt, max_length=150, max_new_tokens=80, patience=2, user=user)
        gameplay = generate_text(gameplay_prompt, max_length=150, max_new_tokens=80, patience=2, user=user)
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
    if use_ai:
        background_prompt = f"Histoire et motivations d'un antagoniste mémorable dans un jeu {game_genre}:"
        gameplay_prompt = f"Les capacités et les tactiques d'un antagoniste dans un jeu {game_genre}:"
        background = generate_text(background_prompt, max_length=150, max_new_tokens=80, patience=2, user=user)
        gameplay = generate_text(gameplay_prompt, max_length=150, max_new_tokens=80, patience=2, user=user)
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

            if use_ai:
                background_prompt = f"Histoire et motivations d'un personnage {role.lower()} dans un jeu {game_genre}:"
                gameplay_prompt = f"Les capacités et l'utilité d'un personnage {role.lower()} dans un jeu {game_genre}:"
                background = generate_text(background_prompt, max_length=150, max_new_tokens=80, patience=2, user=user)
                gameplay = generate_text(gameplay_prompt, max_length=150, max_new_tokens=80, patience=2, user=user)
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


def generate_locations(game_ambiance, count=2, user=None):
    """
    Génère des lieux pour un jeu.

    Args:
        game_ambiance (str): L'ambiance du jeu
        count (int, optional): Nombre de lieux à générer
        user (User, optional): L'utilisateur pour lequel générer les lieux

    Returns:
        list: Une liste de dictionnaires de lieux
    """
    locations = []

    # Get user settings
    user_settings = get_ai_settings(user)

    # Check if we should use AI generation
    use_ai = True

    # If user has no valid AI settings, use random mode
    if user and user.is_authenticated and isinstance(user_settings, UserAISettings):
        if user_settings.ai_service == 'LOCAL' and not MODEL_LOADED:
            use_ai = False
        elif user_settings.ai_service == 'HUGGINGFACE' and not user_settings.huggingface_token:
            use_ai = False
        elif user_settings.ai_service == 'CHATGPT' and not user_settings.chatgpt_token:
            use_ai = False
        elif user_settings.ai_service == 'LMSTUDIO' and not user_settings.lmstudio_url:
            use_ai = False
    elif not MODEL_LOADED:
        use_ai = False

    for i in range(count):
        if use_ai:
            name_prompt = f"Un nom évocateur pour un lieu avec ambiance {game_ambiance}:"
            name = generate_text(name_prompt, max_length=40, max_new_tokens=15, patience=1, user=user)

            desc_prompt = f"Description atmosphérique d'un lieu {game_ambiance} nommé {name}:"
            description = generate_text(desc_prompt, max_length=150, max_new_tokens=80, patience=2, user=user)
        else:
            name = random.choice(LOCATION_NAMES)
            description = f"Un lieu avec une ambiance {game_ambiance.lower()} avec des défis uniques et des secrets à découvrir. L'atmosphère ici reflète le ton général du monde tout en offrant des opportunités de gameplay distinctes."

        locations.append({
            "name": name,
            "description": description
        })

    return locations


def generate_placeholder_image(prompt, image_type, filename, user=None):
    """
    Génère une image en utilisant le service d'IA préféré de l'utilisateur.

    Args:
        prompt (str): Le prompt de génération d'image
        image_type (str): Type d'image (CHARACTER, LOCATION, CONCEPT)
        filename (str): Nom de fichier pour sauvegarder l'image
        user (User, optional): L'utilisateur pour lequel générer l'image

    Returns:
        str: Chemin vers l'image générée
    """
    print("GENERATION D'IMAGE")

    # Get user settings
    user_settings = get_ai_settings(user)

    # Check if user has disabled image generation
    if user and user.is_authenticated and isinstance(user_settings, UserAISettings):
        if not user_settings.generate_images:
            logger.info(f"Génération d'images désactivée pour l'utilisateur {user.username}")
            return generate_fallback_image(prompt, image_type, filename, disabled=True)

    try:
        # Determine which token to use for Hugging Face
        huggingface_token = None

        # If user has Hugging Face settings, use those
        if user and user.is_authenticated and isinstance(user_settings, UserAISettings):
            if user_settings.ai_service == 'HUGGINGFACE' and user_settings.huggingface_token:
                huggingface_token = user_settings.huggingface_token
            elif user_settings.ai_service == 'CHATGPT' and user_settings.chatgpt_token:
                # For ChatGPT users, we can also generate images if they have a token
                # This would use DALL-E, but for now we'll use Hugging Face as a placeholder
                huggingface_token = os.environ.get("HUGGINGFACE_API_KEY")

        # Fallback to environment variable if no user token
        if not huggingface_token:
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


def generate_fallback_image(prompt, image_type, filename, disabled=False):
    """
    Génère une image placeholder avec du texte en cas d'échec de l'API Hugging Face
    ou si la génération d'images est désactivée.

    Args:
        prompt (str): Le prompt de génération d'image
        image_type (str): Type d'image (CHARACTER, LOCATION, CONCEPT)
        filename (str): Nom de fichier pour sauvegarder l'image
        disabled (bool, optional): Si True, indique que la génération d'images est désactivée

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

        # Ajouter une note appropriée selon le cas
        if disabled:
            d.text((50, 500), "Génération d'images désactivée dans les paramètres utilisateur.", 
                   fill=(255, 255, 255), font=font)
            d.text((50, 530), "Activez la génération d'images dans vos paramètres pour générer des images.", 
                   fill=(255, 255, 255), font=font)
        else:
            d.text((50, 500), "Ceci est une image placeholder. Ajoutez un token Hugging Face", 
                   fill=(255, 255, 255), font=font)
            d.text((50, 530), "dans vos paramètres utilisateur pour générer des images avec l'IA.", 
                   fill=(255, 255, 255), font=font)

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

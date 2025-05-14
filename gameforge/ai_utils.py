import random
import os
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

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

def generate_story(genre, ambiance, keywords=None, random_mode=False):
    """
    Generate a story for a game based on genre, ambiance, and keywords.
    
    Args:
        genre (str): The game genre
        ambiance (str): The game ambiance
        keywords (str, optional): Comma-separated keywords
        random_mode (bool, optional): Whether to generate completely random content
        
    Returns:
        dict: A dictionary containing story elements
    """
    # In a real implementation, this would call a text generation API
    # For now, we'll return placeholder content
    
    if random_mode:
        title = random.choice(GAME_TITLES)
    else:
        title = f"{ambiance.title()} {genre.title()}"
    
    story = {
        "title": title,
        "premise": f"In a {ambiance.lower()} world, a hero embarks on an epic {genre.lower()} adventure to save their realm from an ancient evil.",
        "act1": f"The hero discovers their destiny and sets out from their humble beginnings, gathering allies and resources for the journey ahead.",
        "act2": f"Facing increasingly difficult challenges, the hero's resolve is tested. They discover hidden truths about the world and themselves.",
        "act3": f"After overcoming their inner demons, the hero confronts the ultimate evil in an epic showdown that determines the fate of the world.",
        "twist": f"The ancient evil is revealed to be a manifestation of the hero's own fears and doubts, forcing them to confront their true self."
    }
    
    return story

def generate_characters(game_genre, count=2):
    """
    Generate characters for a game.
    
    Args:
        game_genre (str): The game genre
        count (int, optional): Number of characters to generate
        
    Returns:
        list: A list of character dictionaries
    """
    # In a real implementation, this would call a text generation API
    characters = []
    
    # Always include a protagonist
    characters.append({
        "name": random.choice(CHARACTER_NAMES),
        "character_class": random.choice(CHARACTER_CLASSES),
        "role": "Protagonist",
        "background": f"A determined individual with a mysterious past, seeking to find their place in the world.",
        "gameplay": f"Balanced abilities with potential for growth in multiple directions based on player choices."
    })
    
    # Add an antagonist
    characters.append({
        "name": random.choice(CHARACTER_NAMES),
        "character_class": random.choice(CHARACTER_CLASSES),
        "role": "Antagonist",
        "background": f"Once a respected figure who became corrupted by power and now seeks to reshape the world according to their vision.",
        "gameplay": f"Powerful abilities that challenge the player, with unique mechanics that must be understood to defeat."
    })
    
    # Add additional characters if requested
    for i in range(count - 2):
        if i >= 0:  # This check ensures we don't go into negative index if count < 2
            role = random.choice([r for r in CHARACTER_ROLES if r not in ["Protagonist", "Antagonist"]])
            characters.append({
                "name": random.choice(CHARACTER_NAMES),
                "character_class": random.choice(CHARACTER_CLASSES),
                "role": role,
                "background": f"A unique individual with their own motivations and history, whose path crosses with the protagonist.",
                "gameplay": f"Specialized abilities that complement the team and provide strategic options in various situations."
            })
    
    return characters

def generate_locations(game_ambiance, count=2):
    """
    Generate locations for a game.
    
    Args:
        game_ambiance (str): The game ambiance
        count (int, optional): Number of locations to generate
        
    Returns:
        list: A list of location dictionaries
    """
    # In a real implementation, this would call a text generation API
    locations = []
    
    for i in range(count):
        name = random.choice(LOCATION_NAMES)
        locations.append({
            "name": name,
            "description": f"A {game_ambiance.lower()} location with unique challenges and secrets to discover. The atmosphere here reflects the overall tone of the world while providing distinct gameplay opportunities."
        })
    
    return locations

def generate_placeholder_image(prompt, image_type, filename):
    """
    Generate a placeholder image with text.
    In a real implementation, this would call an image generation API.
    
    Args:
        prompt (str): The image generation prompt
        image_type (str): Type of image (CHARACTER, LOCATION, CONCEPT)
        filename (str): Filename to save the image
        
    Returns:
        str: Path to the generated image
    """
    try:
        # Create a colored background based on image type
        if image_type == 'CHARACTER':
            bg_color = (100, 100, 200)  # Blue for characters
        elif image_type == 'LOCATION':
            bg_color = (100, 200, 100)  # Green for locations
        else:
            bg_color = (200, 100, 100)  # Red for concepts
        
        # Create a simple image with text
        img = Image.new('RGB', (800, 600), color=bg_color)
        d = ImageDraw.Draw(img)
        
        # Try to use a system font
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            font = ImageFont.load_default()
        
        # Add the prompt text
        d.text((50, 50), f"Image Type: {image_type}", fill=(255, 255, 255), font=font)
        
        # Wrap the prompt text
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
        
        # Draw the wrapped text
        y_position = 100
        for line in lines:
            d.text((50, y_position), line, fill=(255, 255, 255), font=font)
            y_position += 30
        
        # Add a note that this is a placeholder
        d.text((50, 500), "This is a placeholder image. In a real implementation,", fill=(255, 255, 255), font=font)
        d.text((50, 530), "this would be generated by an AI model.", fill=(255, 255, 255), font=font)
        
        # Save the image
        media_path = os.path.join(settings.MEDIA_ROOT, 'game_images', filename)
        img.save(media_path)
        
        # Return the relative path for the database
        return os.path.join('game_images', filename)
    
    except Exception as e:
        logger.error(f"Error generating placeholder image: {e}")
        # Return a default image path in case of error
        return 'game_images/placeholder.jpg'
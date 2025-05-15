from django.db import models
from django.contrib.auth.models import User
from django.core.cache import cache

# Create your models here.
class Game(models.Model):
    GENRE_CHOICES = [
        ('RPG', 'Jeu de Rôle'),
        ('FPS', 'Tir à la Première Personne'),
        ('ADVENTURE', 'Aventure'),
        ('STRATEGY', 'Stratégie'),
        ('SIMULATION', 'Simulation'),
        ('PUZZLE', 'Puzzle'),
        ('PLATFORMER', 'Plateforme'),
        ('METROIDVANIA', 'Metroidvania'),
        ('VISUAL_NOVEL', 'Roman Visuel'),
        ('MMORPG', 'Jeu de Rôle en Ligne Massivement Multijoueur'),
        ('MOBA', 'Arène de Bataille en Ligne Multijoueur'),
        ('BATTLE_ROYALE', 'Battle Royale'),
        ('SURVIVAL', 'Survie'),
        ('RACING', 'Course'),
        ('SPORTS', 'Sports'),
        ('FIGHTING', 'Combat'),
        ('RHYTHM', 'Rythme'),
        ('ROGUELIKE', 'Roguelike'),
        ('SANDBOX', 'Bac à Sable'),
        ('TOWER_DEFENSE', 'Défense de Tour'),
        ('CARD_GAME', 'Jeu de Cartes'),
        ('BOARD_GAME', 'Jeu de Plateau'),
        ('IDLE', 'Jeu Incrémental'),
        ('EDUCATIONAL', 'Éducatif'),
        ('OTHER', 'Autre'),
    ]

    AMBIANCE_CHOICES = [
        ('POST_APOCALYPTIC', 'Post-Apocalyptique'),
        ('FANTASY', 'Fantaisie'),
        ('SCI_FI', 'Science-Fiction'),
        ('CYBERPUNK', 'Cyberpunk'),
        ('HORROR', 'Horreur'),
        ('MYSTERY', 'Mystère'),
        ('HISTORICAL', 'Historique'),
        ('STEAMPUNK', 'Steampunk'),
        ('DREAMLIKE', 'Onirique'),
        ('DARK_FANTASY', 'Fantasy Sombre'),
        ('MEDIEVAL', 'Médiéval'),
        ('WESTERN', 'Western'),
        ('NOIR', 'Film Noir'),
        ('SUPERHERO', 'Super-héros'),
        ('COMEDY', 'Comédie'),
        ('DYSTOPIAN', 'Dystopique'),
        ('UTOPIAN', 'Utopique'),
        ('MYTHOLOGICAL', 'Mythologique'),
        ('LOVECRAFTIAN', 'Lovecraftien'),
        ('SPACE_OPERA', 'Space Opera'),
        ('MILITARY', 'Militaire'),
        ('UNDERWATER', 'Sous-marin'),
        ('TROPICAL', 'Tropical'),
        ('ARCTIC', 'Arctique'),
        ('DESERT', 'Désertique'),
        ('URBAN', 'Urbain'),
        ('RURAL', 'Rural'),
        ('OTHER', 'Autre'),
    ]

    title = models.CharField(max_length=100, verbose_name="Titre")
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='games', verbose_name="Créateur")
    genre = models.CharField(max_length=20, choices=GENRE_CHOICES, verbose_name="Genre")
    ambiance = models.CharField(max_length=20, choices=AMBIANCE_CHOICES, verbose_name="Ambiance")
    keywords = models.CharField(max_length=200, help_text="Mots-clés séparés par des virgules", verbose_name="Mots-clés")
    references = models.CharField(max_length=200, blank=True, help_text="Références séparées par des virgules", verbose_name="Références")

    # Structure de l'histoire
    story_premise = models.TextField(verbose_name="Prémisse de l'histoire")
    story_act1 = models.TextField(verbose_name="Acte 1")
    story_act2 = models.TextField(verbose_name="Acte 2")
    story_act3 = models.TextField(verbose_name="Acte 3")
    story_twist = models.TextField(verbose_name="Rebondissement")

    # Paramètres du jeu
    is_public = models.BooleanField(default=True, verbose_name="Public")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Mis à jour le")

    def __str__(self):
        return self.title

class Character(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='characters', verbose_name="Jeu")
    name = models.CharField(max_length=100, verbose_name="Nom")
    character_class = models.CharField(max_length=100, verbose_name="Classe")
    role = models.CharField(max_length=100, verbose_name="Rôle")
    background = models.TextField(verbose_name="Histoire")
    gameplay = models.TextField(verbose_name="Gameplay")

    class Meta:
        verbose_name = "Personnage"
        verbose_name_plural = "Personnages"

    def __str__(self):
        return f"{self.name} ({self.game.title})"

class Location(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='locations', verbose_name="Jeu")
    name = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(verbose_name="Description")

    class Meta:
        verbose_name = "Lieu"
        verbose_name_plural = "Lieux"

    def __str__(self):
        return f"{self.name} ({self.game.title})"

class GameImage(models.Model):
    IMAGE_TYPE_CHOICES = [
        ('CHARACTER', 'Personnage'),
        ('LOCATION', 'Lieu'),
        ('CONCEPT', 'Art Conceptuel'),
    ]

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='images', verbose_name="Jeu")
    image_type = models.CharField(max_length=20, choices=IMAGE_TYPE_CHOICES, verbose_name="Type d'image")
    image = models.ImageField(upload_to='game_images/', verbose_name="Image")
    prompt = models.TextField(help_text="Le prompt utilisé pour générer cette image", verbose_name="Prompt")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")

    class Meta:
        verbose_name = "Image de jeu"
        verbose_name_plural = "Images de jeu"

    def __str__(self):
        return f"{self.get_image_type_display()} pour {self.game.title}"

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites', verbose_name="Utilisateur")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='favorited_by', verbose_name="Jeu")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        unique_together = ('user', 'game')
        verbose_name = "Favori"
        verbose_name_plural = "Favoris"

    def __str__(self):
        return f"{self.user.username} a ajouté {self.game.title} aux favoris"

class AISettings(models.Model):
    """Modèle pour stocker les paramètres d'IA pour l'application."""
    use_remote_llm = models.BooleanField(default=False, 
                                        help_text="Utiliser un LLM distant au lieu du modèle local", 
                                        verbose_name="Utiliser LLM distant")
    remote_llm_url = models.CharField(max_length=255, default="http://176.144.45.42:80",
                                     help_text="URL de l'API LLM distante",
                                     verbose_name="URL du LLM distant")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Mis à jour le")

    class Meta:
        verbose_name = "Paramètres d'IA"
        verbose_name_plural = "Paramètres d'IA""Modèle pour stocker les paramètres d'IA pour l'application."""
    use_remote_llm = models.BooleanField(default=False,
                                        help_text="Utiliser un LLM distant au lieu du modèle local",
                                        verbose_name="Utiliser LLM distant")
    remote_llm_url = models.CharField(max_length=255, default="http://127.0.0.1:1234",
                                     help_text="URL de l'API LLM distante",
                                     verbose_name="URL du LLM distant")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.Date

    def save(self, *args, **kwargs):
        # Ensure there's only one instance of AISettings
        if not self.pk and AISettings.objects.exists():
            # If you're trying to create a new object and one already exists,
            # update the existing one instead
            self.pk = AISettings.objects.first().pk

        # Clear the cache when settings are updated
        cache.delete('ai_settings')

        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Get the AI settings, using cache if available."""
        settings = cache.get('ai_settings')
        if settings is None:
            settings, created = cls.objects.get_or_create(pk=1)
            cache.set('ai_settings', settings)
        return settings

    def __str__(self):
        return "AI Settings"

from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Game(models.Model):
    GENRE_CHOICES = [
        ('RPG', 'Role-Playing Game'),
        ('FPS', 'First-Person Shooter'),
        ('ADVENTURE', 'Adventure'),
        ('STRATEGY', 'Strategy'),
        ('SIMULATION', 'Simulation'),
        ('PUZZLE', 'Puzzle'),
        ('PLATFORMER', 'Platformer'),
        ('METROIDVANIA', 'Metroidvania'),
        ('VISUAL_NOVEL', 'Visual Novel'),
        ('OTHER', 'Other'),
    ]

    AMBIANCE_CHOICES = [
        ('POST_APOCALYPTIC', 'Post-Apocalyptic'),
        ('FANTASY', 'Fantasy'),
        ('SCI_FI', 'Science Fiction'),
        ('CYBERPUNK', 'Cyberpunk'),
        ('HORROR', 'Horror'),
        ('MYSTERY', 'Mystery'),
        ('HISTORICAL', 'Historical'),
        ('STEAMPUNK', 'Steampunk'),
        ('DREAMLIKE', 'Dreamlike'),
        ('DARK_FANTASY', 'Dark Fantasy'),
        ('OTHER', 'Other'),
    ]

    title = models.CharField(max_length=100)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='games')
    genre = models.CharField(max_length=20, choices=GENRE_CHOICES)
    ambiance = models.CharField(max_length=20, choices=AMBIANCE_CHOICES)
    keywords = models.CharField(max_length=200, help_text="Comma-separated keywords")
    references = models.CharField(max_length=200, blank=True, help_text="Comma-separated references")

    # Story structure
    story_premise = models.TextField()
    story_act1 = models.TextField()
    story_act2 = models.TextField()
    story_act3 = models.TextField()
    story_twist = models.TextField()

    # Game settings
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class Character(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='characters')
    name = models.CharField(max_length=100)
    character_class = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    background = models.TextField()
    gameplay = models.TextField()

    def __str__(self):
        return f"{self.name} ({self.game.title})"

class Location(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return f"{self.name} ({self.game.title})"

class GameImage(models.Model):
    IMAGE_TYPE_CHOICES = [
        ('CHARACTER', 'Character'),
        ('LOCATION', 'Location'),
        ('CONCEPT', 'Concept Art'),
    ]

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='images')
    image_type = models.CharField(max_length=20, choices=IMAGE_TYPE_CHOICES)
    image = models.ImageField(upload_to='game_images/')
    prompt = models.TextField(help_text="The prompt used to generate this image")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_image_type_display()} image for {self.game.title}"

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'game')

    def __str__(self):
        return f"{self.user.username} favorited {self.game.title}"

import uuid

from django.contrib.auth import logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .ai_utils import generate_story, generate_characters, generate_locations, generate_placeholder_image
from .models import Game, Character, Location, GameImage, Favorite
from .forms import GameForm

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create your views here.
def home(request):
    """Home page view showing all public games"""
    games = Game.objects.filter(is_public=True).exclude(is_public=0).order_by('-created_at')
    return render(request, 'gameforge/home.html', {'games': games})

def register(request):
    """User registration view"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Compte créé pour {username}! Vous pouvez maintenant vous connecter.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'gameforge/register.html', {'form': form})

@login_required
def dashboard(request):
    """Dashboard view showing all games created by the current user"""
    games = Game.objects.filter(creator=request.user).order_by('-created_at')
    return render(request, 'gameforge/dashboard.html', {'games': games})

def game_detail(request, game_id):
    """Game detail view showing all information about a specific game"""
    game = get_object_or_404(Game, id=game_id)

    # Check if the game is private and the user is not the creator
    if not game.is_public and (not request.user.is_authenticated or request.user != game.creator):
        messages.error(request, "Vous n'avez pas la permission de voir ce jeu.")
        return redirect('home')

    # Check if the game is in the user's favorites
    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(user=request.user, game=game).exists()

    characters = game.characters.all()
    locations = game.locations.all()
    images = game.images.all()

    return render(request, 'gameforge/game_detail.html', {
        'game': game,
        'characters': characters,
        'locations': locations,
        'images': images,
        'is_favorite': is_favorite
    })

@login_required
def create_game(request):
    """View for creating a new game"""
    if request.method == 'POST':
        form = GameForm(request.POST)
        if form.is_valid():
            game = form.save(commit=False)
            game.creator = request.user
            game.save()

            # Generate game content using AI
            generate_game_content(game)

            messages.success(request, f'Jeu "{game.title}" créé avec succès!')
            return redirect('game_detail', game_id=game.id)
    else:
        form = GameForm()

    return render(request, 'gameforge/create_game.html', {'form': form})

@login_required
def edit_game(request, game_id):
    """View for editing an existing game"""
    game = get_object_or_404(Game, id=game_id)

    # Check if the user is the creator of the game
    if request.user != game.creator:
        messages.error(request, "Vous n'avez pas la permission de modifier ce jeu.")
        return redirect('game_detail', game_id=game.id)

    if request.method == 'POST':
        form = GameForm(request.POST, instance=game)
        if form.is_valid():
            form.save()
            messages.success(request, f'Jeu "{game.title}" mis à jour avec succès!')
            return redirect('game_detail', game_id=game.id)
    else:
        form = GameForm(instance=game)

    return render(request, 'gameforge/edit_game.html', {'form': form, 'game': game})

@login_required
def delete_game(request, game_id):
    """View for deleting an existing game"""
    game = get_object_or_404(Game, id=game_id)

    # Check if the user is the creator of the game
    if request.user != game.creator:
        messages.error(request, "Vous n'avez pas la permission de supprimer ce jeu.")
        return redirect('game_detail', game_id=game.id)

    if request.method == 'POST':
        game.delete()
        messages.success(request, f'Jeu "{game.title}" supprimé avec succès!')
        return redirect('dashboard')

    return render(request, 'gameforge/delete_game.html', {'game': game})

@login_required
def favorites(request):
    """View for showing all games favorited by the current user"""
    favorites = Favorite.objects.filter(user=request.user).select_related('game').order_by('-created_at')
    return render(request, 'gameforge/favorites.html', {'favorites': favorites})

@login_required
@require_POST
def toggle_favorite(request, game_id):
    """AJAX view for toggling a game as favorite"""
    game = get_object_or_404(Game, id=game_id)

    # Check if the game is private and the user is not the creator
    if not game.is_public and request.user != game.creator:
        return JsonResponse({'status': 'error', 'message': "Vous n'avez pas la permission d'ajouter ce jeu aux favoris."})

    favorite, created = Favorite.objects.get_or_create(user=request.user, game=game)

    if not created:
        # If the favorite already existed, delete it
        favorite.delete()
        return JsonResponse({'status': 'success', 'is_favorite': False})

    return JsonResponse({'status': 'success', 'is_favorite': True})

@login_required
def random_game(request):
    """View for generating a random game"""
    if request.method == 'POST':
        # Create a new game with random parameters
        game = Game.objects.create(
            title="Random Game",
            creator=request.user,
            genre=Game.GENRE_CHOICES[0][0],  # Default to first genre
            ambiance=Game.AMBIANCE_CHOICES[0][0],  # Default to first ambiance
            keywords="random, generated",
            story_premise="To be generated...",
            story_act1="To be generated...",
            story_act2="To be generated...",
            story_act3="To be generated...",
            story_twist="To be generated..."
        )

        # Generate game content using AI
        generate_game_content(game, random=True)

        messages.success(request, f'Jeu aléatoire "{game.title}" créé avec succès!')
        return redirect('game_detail', game_id=game.id)

    return render(request, 'gameforge/random_game.html')


def generate_game_content(game, random=False):
    """Helper function to generate game content using AI"""
    # Utiliser les fonctions AI pour générer du contenu

    # Générer l'histoire avec l'IA
    story = generate_story(
        title=game.title,
        genre=game.genre,
        ambiance=game.ambiance,
        keywords=game.keywords,
        refs=game.references,
        random_mode=random
    )

    # Mettre à jour les champs du jeu avec l'histoire générée
    game.title = story["title"] if random else game.title
    game.story_premise = story["premise"]
    game.story_act1 = story["act1"]
    game.story_act2 = story["act2"]
    game.story_act3 = story["act3"]
    game.story_twist = story["twist"]
    game.save()

    # Générer des personnages avec l'IA (2 par défaut: un protagoniste et un antagoniste)
    characters = generate_characters(game_genre=game.genre, count=2)

    # Créer les objets Character dans la base de données
    for char_data in characters:
        Character.objects.create(
            game=game,
            name=char_data["name"],
            character_class=char_data["character_class"],
            role=char_data["role"],
            background=char_data["background"],
            gameplay=char_data["gameplay"]
        )

    # Générer des lieux avec l'IA
    locations = generate_locations(game_ambiance=game.ambiance, count=2)

    # Créer les objets Location dans la base de données
    for loc_data in locations:
        Location.objects.create(
            game=game,
            name=loc_data["name"],
            description=loc_data["description"]
        )

    # Générer des images placeholder pour les personnages et les lieux
    # (dans un déploiement réel, vous appelleriez une API de génération d'images)

    # Image pour le protagoniste
    char_prompt = f"Un héros de type {game.genre} dans un univers {game.ambiance}"
    char_filename = f"character_{game.id}_{uuid.uuid4().hex}.jpg"
    char_image_path = generate_placeholder_image(
        prompt=char_prompt,
        image_type="CHARACTER",
        filename=char_filename
    )

    # Créer l'objet GameImage pour le personnage
    GameImage.objects.create(
        game=game,
        image_type="CHARACTER",
        prompt=char_prompt,
        image=char_image_path
    )

    # Image pour un lieu
    loc_prompt = f"Un lieu d'ambiance {game.ambiance} pour une aventure de type {game.genre}"
    loc_filename = f"location_{game.id}_{uuid.uuid4().hex}.jpg"
    loc_image_path = generate_placeholder_image(
        prompt=loc_prompt,
        image_type="LOCATION",
        filename=loc_filename
    )

    # Créer l'objet GameImage pour le lieu
    GameImage.objects.create(
        game=game,
        image_type="LOCATION",
        prompt=loc_prompt,
        image=loc_image_path
    )

def logout_view(request):
    logout(request)
    return redirect('login')

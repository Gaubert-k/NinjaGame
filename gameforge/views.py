from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count

from .models import Game, Character, Location, GameImage, Favorite
from .forms import GameForm, CharacterForm, LocationForm, GameImageForm

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create your views here.
def home(request):
    """Home page view showing all public games"""
    games = Game.objects.filter(is_public=True).order_by('-created_at')
    return render(request, 'gameforge/home.html', {'games': games})

def register(request):
    """User registration view"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
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
        messages.error(request, "You don't have permission to view this game.")
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

            messages.success(request, f'Game "{game.title}" created successfully!')
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
        messages.error(request, "You don't have permission to edit this game.")
        return redirect('game_detail', game_id=game.id)

    if request.method == 'POST':
        form = GameForm(request.POST, instance=game)
        if form.is_valid():
            form.save()
            messages.success(request, f'Game "{game.title}" updated successfully!')
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
        messages.error(request, "You don't have permission to delete this game.")
        return redirect('game_detail', game_id=game.id)

    if request.method == 'POST':
        game.delete()
        messages.success(request, f'Game "{game.title}" deleted successfully!')
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
        return JsonResponse({'status': 'error', 'message': "You don't have permission to favorite this game."})

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

        messages.success(request, f'Random game "{game.title}" created successfully!')
        return redirect('game_detail', game_id=game.id)

    return render(request, 'gameforge/random_game.html')

def generate_game_content(game, random=False):
    """Helper function to generate game content using AI"""
    # This is a placeholder for the actual AI integration
    # In a real implementation, this would call the Hugging Face API

    # For now, we'll just create some dummy content
    if random:
        game.title = "Randomly Generated Adventure"
        game.genre = Game.GENRE_CHOICES[2][0]  # Adventure
        game.ambiance = Game.AMBIANCE_CHOICES[1][0]  # Fantasy
        game.keywords = "random, adventure, fantasy"

    # Generate story
    game.story_premise = "A hero embarks on a journey to save the world from an ancient evil."
    game.story_act1 = "The hero discovers their destiny and sets out on a quest."
    game.story_act2 = "The hero faces challenges and makes allies along the way."
    game.story_act3 = "The hero confronts the ancient evil in an epic battle."
    game.story_twist = "The ancient evil is revealed to be the hero's long-lost relative."
    game.save()

    # Generate characters
    Character.objects.create(
        game=game,
        name="Hero",
        character_class="Warrior",
        role="Protagonist",
        background="A simple farmer who discovers they have a great destiny.",
        gameplay="Strong melee attacks and defensive abilities."
    )

    Character.objects.create(
        game=game,
        name="Villain",
        character_class="Sorcerer",
        role="Antagonist",
        background="An ancient evil seeking to conquer the world.",
        gameplay="Powerful magic attacks and summoning abilities."
    )

    # Generate locations
    Location.objects.create(
        game=game,
        name="Starting Village",
        description="A peaceful village where the hero begins their journey."
    )

    Location.objects.create(
        game=game,
        name="Ancient Temple",
        description="A mysterious temple filled with traps and treasures."
    )

    # In a real implementation, we would also generate images using an AI model
    # For now, we'll just create placeholder entries
    GameImage.objects.create(
        game=game,
        image_type="CHARACTER",
        prompt="A heroic warrior with a sword and shield",
        image="placeholder.jpg"  # This would be replaced with an actual generated image
    )

    GameImage.objects.create(
        game=game,
        image_type="LOCATION",
        prompt="An ancient temple in a lush forest",
        image="placeholder.jpg"  # This would be replaced with an actual generated image
    )

from django import forms
from .models import Game, Character, Location, GameImage

class GameForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = ['title', 'genre', 'ambiance', 'keywords', 'references', 'is_public']
        widgets = {
            'keywords': forms.TextInput(attrs={'placeholder': 'Entrez des mots-clés séparés par des virgules'}),
            'references': forms.TextInput(attrs={'placeholder': 'Entrez des références séparées par des virgules (optionnel)'}),
        }
        labels = {
            'title': 'Titre',
            'genre': 'Genre',
            'ambiance': 'Ambiance',
            'keywords': 'Mots-clés',
            'references': 'Références',
            'is_public': 'Public',
        }

class CharacterForm(forms.ModelForm):
    class Meta:
        model = Character
        fields = ['name', 'character_class', 'role', 'background', 'gameplay']
        widgets = {
            'background': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Histoire du personnage'}),
            'gameplay': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Mécaniques de gameplay du personnage'}),
        }
        labels = {
            'name': 'Nom',
            'character_class': 'Classe',
            'role': 'Rôle',
            'background': 'Histoire',
            'gameplay': 'Gameplay',
        }

class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Description détaillée du lieu'}),
        }
        labels = {
            'name': 'Nom',
            'description': 'Description',
        }

class GameImageForm(forms.ModelForm):
    class Meta:
        model = GameImage
        fields = ['image_type', 'prompt']
        widgets = {
            'prompt': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Entrez une description détaillée pour la génération d\'image'}),
        }
        labels = {
            'image_type': 'Type d\'image',
            'prompt': 'Prompt',
        }

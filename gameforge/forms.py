from django import forms
from .models import Game, Character, Location, GameImage

class GameForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = ['title', 'genre', 'ambiance', 'keywords', 'references', 'is_public']
        widgets = {
            'keywords': forms.TextInput(attrs={'placeholder': 'Enter keywords separated by commas'}),
            'references': forms.TextInput(attrs={'placeholder': 'Enter references separated by commas (optional)'}),
        }

class CharacterForm(forms.ModelForm):
    class Meta:
        model = Character
        fields = ['name', 'character_class', 'role', 'background', 'gameplay']
        widgets = {
            'background': forms.Textarea(attrs={'rows': 4}),
            'gameplay': forms.Textarea(attrs={'rows': 4}),
        }

class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

class GameImageForm(forms.ModelForm):
    class Meta:
        model = GameImage
        fields = ['image_type', 'prompt']
        widgets = {
            'prompt': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter a detailed description for the image generation'}),
        }
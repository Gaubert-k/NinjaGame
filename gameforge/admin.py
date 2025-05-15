from django.contrib import admin
from .models import Game, Character, Location, GameImage, Favorite, AISettings

# Register your models here.
class CharacterInline(admin.TabularInline):
    model = Character
    extra = 1

class LocationInline(admin.TabularInline):
    model = Location
    extra = 1

class GameImageInline(admin.TabularInline):
    model = GameImage
    extra = 1

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'genre', 'ambiance', 'is_public', 'created_at')
    list_filter = ('genre', 'ambiance', 'is_public', 'created_at')
    search_fields = ('title', 'creator__username', 'keywords')
    inlines = [CharacterInline, LocationInline, GameImageInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(creator=request.user)

@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ('name', 'game', 'character_class', 'role')
    list_filter = ('character_class', 'role')
    search_fields = ('name', 'game__title')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'game')
    search_fields = ('name', 'game__title')

@admin.register(GameImage)
class GameImageAdmin(admin.ModelAdmin):
    list_display = ('game', 'image_type', 'created_at')
    list_filter = ('image_type', 'created_at')
    search_fields = ('game__title', 'prompt')

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'game', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'game__title')

@admin.register(AISettings)
class AISettingsAdmin(admin.ModelAdmin):
    list_display = ('use_remote_llm', 'remote_llm_url', 'updated_at')

    def has_add_permission(self, request):
        # Only allow adding if no AISettings exist yet
        return not AISettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of the settings
        return False

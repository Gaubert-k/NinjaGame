from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Authentication URLs
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='gameforge/login.html'), name='login'),
    #path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('logout/', views.logout_view, name='logout'),
    # Game URLs
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('game/<int:game_id>/', views.game_detail, name='game_detail'),
    path('game/create/', views.create_game, name='create_game'),
    path('game/<int:game_id>/edit/', views.edit_game, name='edit_game'),
    path('game/<int:game_id>/delete/', views.delete_game, name='delete_game'),

    path('favorites/', views.favorites, name='favorites'),
    path('game/<int:game_id>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),

    path('random-game/', views.random_game, name='random_game'),

    # AI Settings URL
    path('ai-settings/', views.ai_settings, name='ai_settings'),
]

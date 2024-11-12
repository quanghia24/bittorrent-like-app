from django.urls import path, include
from . import views

urlpatterns = [
    path('create-user/', views.create_user, name='create-user'),
    path('login-user/', views.login_user, name='login-user'),
    path('logout-user/', views.logout_user, name='logout_user'),
    path('add-filename/', views.add_filenames, name='add-filename'),
    path('get-peer-list/', views.get_peer_list, name='get-peers-have-filename'),
    path('update-freq/', views.update_freq, name='update-freq'),
]

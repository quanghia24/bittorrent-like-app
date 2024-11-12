from django.contrib import admin
from .models import CustomUser, Peer, Torrent
# Register your models here.
admin.site.register(CustomUser)
admin.site.register(Peer)
admin.site.register(Torrent)


from django.contrib import admin
from .models import CustomUser, Peer
# Register your models here.
admin.site.register(CustomUser)
admin.site.register(Peer)


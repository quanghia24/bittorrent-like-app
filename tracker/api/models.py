from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
import json
from datetime import datetime
class CustomUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username field must be set")
        user = self.model(username=username, **extra_fields)
        user.set_password(password)  # Hash the password
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True, primary_key=True)
    password = models.CharField(max_length=128)  # This will store the hashed password
    freq = models.PositiveIntegerField(default=0)
      # Store filenames as a JSON array

    # Required fields for superuser/admin functionality
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'

    def update_freq(self):
        self.freq += 1
        self.save()

    def __str__(self) -> str:
        return f"{self.username} {self.freq}"

class Peer(models.Model):
    node_id = models.CharField(max_length=10, unique=True)
    address = models.CharField(max_length=25)
    user = models.OneToOneField(CustomUser, related_name="peer", on_delete=models.CASCADE)
    torrents = models.JSONField(default=list, blank=True)
    last_seen = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__ (self):
        if self.is_active:
            return self.user.username + f" [freq:{str(self.user.freq)}]"
        else:
            
            return self.user.username + " [Inactive]"
    
    def update_last_seen(self):
        self.last_seen = datetime.now()
        self.is_active = True
        self.save()
    # def mark_inactive(self):
    #     self.is_active = False
    #     self.save()

    
    def add_torrent(self, info_hash:str):
        if info_hash not in self.torrents:
            self.torrents.append(info_hash)
            print(f"{self.user.username} - added torrent {info_hash}")
            self.save()


    def get_torrents(self):
        return self.torrents

class Torrent(models.Model):
    peer = models.ForeignKey(Peer, related_name="torrent_owner", on_delete=models.CASCADE)
    name = models.CharField(max_length=15)
    info_hash = models.TextField()
    filenames = models.JSONField(default=list, blank=True)
    piece_length = models.IntegerField()

    def add_file(self, file:dict):
        if not isinstance(file, dict) or 'path' not in file or 'length' not in file:
            raise ValueError("File must be a dictionary with 'path' and 'length' keys.")

        file_list = self.filenames  # This will be a Python list
        if file not in file_list:
            file_list.append(file)

        self.filenames = file_list
        self.save()

    def get_files(self) -> list:
        return json.loads(self.filenames)

    def __str__(self):
        return self.name + " by " + self.peer.user.username


from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
import json

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
      # Store filenames as a JSON array

    # Required fields for superuser/admin functionality
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'

class Peer(models.Model):
    address = models.CharField(max_length=25)
    freq = models.PositiveIntegerField(default=0)
    filenames = models.TextField(default="[]")
    user = models.OneToOneField(CustomUser, related_name="peer", on_delete=models.CASCADE)

    def __str__ (self):
        return self.user.username + f" [freq:{str(self.freq)}]"
    
    def add_filename(self, filename):
        files = filename.split()
        filenames_list = json.loads(self.filenames)
        for file in files:
            if file not in filenames_list:
                filenames_list.append(file)
                print(f"{self.user.username} - added {file}")
        self.filenames = json.dumps(filenames_list)
        self.save()

    def update_freq(self):
        self.freq += 1
        self.save()

    def get_filenames(self):
        return json.loads(self.filenames)

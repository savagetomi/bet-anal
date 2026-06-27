from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

from user.manager import UserManager

# Create your models here.

class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    username = models.CharField(max_length=30, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} created account with {self.email}"


    objects = UserManager()
    
class Bet(models.Model):
    BET_RESULTS = (
        ('pending', 'Pending'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='bets')
    bet_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    stake = models.DecimalField(max_digits=10, decimal_places=2)
    potential_payout = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    game_type = models.CharField(max_length=50)
    number_of_games = models.CharField(max_length=3, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(choices=BET_RESULTS, max_length=50, null=True, blank=True, default='pending')

    def __str__(self):
        return f"Bet {self.bet_id} - {self.user.username}"

    def profit_loss(self):
        if self.result == 'won':
            return self.potential_payout - self.stake
        elif self.result == 'lost':
            return -self.stake
        else:
            return "Bet is Pending"
    

    


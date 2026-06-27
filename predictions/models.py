from django.db import models
import uuid

# Create your models here.
class Sports(models.TextChoices):
    FOOTBALL = 'football', 'Football'
    BASKETBALL = 'basketball', 'Basketball'
    TENNIS = 'tennis', 'Tennis'

class Fixtures(models.Model):
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('live', 'Live'),
        ('finished', 'Finished'),
        ('postponed', 'Postponed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sport = models.CharField(max_length=50, choices=Sports.choices)
    provider = models.CharField(max_length=100)
    provider_fixture_id = models.CharField(max_length=100)
    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    kickoff_time = models.DateTimeField()
    league = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    
    class Meta:
        unique_together = ('provider', 'provider_fixture_id')
        indexes = [
            models.Index(fields=['sport', 'kickoff_time']),
        ]

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} - {self.sport} - {self.kickoff_time}"
    
class Oddsnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fixture = models.ForeignKey(Fixtures, on_delete=models.CASCADE, related_name='odds')
    bookmaker = models.CharField(max_length=100)
    home_odds = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    draw_odds = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    away_odds = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.fixture} - {self.bookmaker} - {self.captured_at}"

class TeamForm(models.Model):
    fixture = models.ForeignKey(Fixtures, on_delete=models.CASCADE, related_name='form_stats')
    team_name = models.CharField(max_length=150)
    is_home_team = models.BooleanField()
    wins_last_5 = models.IntegerField(default=0)
    draws_last_5 = models.IntegerField(default=0)
    losses_last_5 = models.IntegerField(default=0)
    goals_for_avg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    goals_against_avg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    head_to_head_summary = models.JSONField(default=dict, blank=True)
    injuries = models.JSONField(default=list, blank=True)
    computed_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.team_name} Form for {self.fixture}"


class Prediction(models.Model):
    OUTCOME_CHOICES = (
        ('home_win', 'Home win'),
        ('away_win', 'Away win'),
        ('draw', 'Draw'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fixture = models.ForeignKey(Fixtures, on_delete=models.CASCADE, related_name='predictions')
    predicted_outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES)
    confidence = models.DecimalField(max_digits=5, decimal_places=2)
    reasoning = models.TextField()
    model_used = models.CharField(max_length=100, default='claude-sonnet-4-6')
    was_correct = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.fixture} - {self.predicted_outcome} ({self.confidence}%)"

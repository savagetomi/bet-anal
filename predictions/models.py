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
        return f"Prediction for {self.fixture} ({self.confidence}%)"

    def grade(self):
        """
        Compares each predicted outcome against the fixture's actual result
        and fills in was_correct for every entry in outcomes.
        Only call this once the fixture has finished and has scores recorded.
        """
        if self.fixture.status != 'finished':
            raise ValueError(
                f"Cannot grade prediction for {self.fixture} - "
                f"fixture status is '{self.fixture.status}', not 'finished'."
            )
        if self.fixture.home_score is None or self.fixture.away_score is None:
            raise ValueError(
                f"Cannot grade prediction for {self.fixture} - "
                f"fixture is marked finished but has no recorded score."
            )

        actual = self._determine_actual_result()

        for market, entry in self.outcomes.items():
            entry['was_correct'] = self._grade_one_market(
                market,
                entry.get('pick'),
                actual
            )

        # update_fields limits the SQL UPDATE to only the outcomes column -
        # prevents accidentally overwriting other fields that may have changed
        # concurrently between when this Prediction was loaded and now.
        self.save(update_fields=['outcomes'])

    def _determine_actual_result(self) -> dict:
        """
        Builds a plain dict describing what actually happened.
        Called once per grade() so every market reads the same source of truth.
        """
        home = self.fixture.home_score
        away = self.fixture.away_score

        if home > away:
            winner = 'home_win'
        elif away > home:
            winner = 'away_win'
        else:
            winner = 'draw'

        return {
            'winner': winner,
            'home_score': home,
            'away_score': away,
        }

    def _grade_one_market(self, market: str, pick, actual: dict):
        """
        Grades ONE market type against the actual result.
        Returns True, False, or None.
        None means "we can't grade this yet" - honest unknown,
        not a wrong answer. New market types just need a new elif here.
        """
        if market == '1x2':
            return pick == actual['winner']

        if market == 'double_chance':
            if pick == 'home_or_draw':
                return actual['winner'] in ('home_win', 'draw')
            if pick == 'away_or_draw':
                return actual['winner'] in ('away_win', 'draw')
            if pick == 'home_or_away':
                return actual['winner'] in ('home_win', 'away_win')
            return None

        if market == 'correct_score':
            actual_score = f"{actual['home_score']}-{actual['away_score']}"
            return pick == actual_score

        if market == 'btts':
            both_scored = actual['home_score'] > 0 and actual['away_score'] > 0
            if pick == 'yes':
                return both_scored
            if pick == 'no':
                return not both_scored
            return None

        if market == 'handicap':
            if not isinstance(pick, dict):
                return None
            line = pick.get('line')
            side = pick.get('side')
            if line is None or side not in ('home', 'away'):
                return None
            adjusted_home = actual['home_score'] + (line if side == 'home' else 0)
            adjusted_away = actual['away_score'] + (line if side == 'away' else 0)
            if side == 'home':
                return adjusted_home > adjusted_away
            return adjusted_away > adjusted_home

        # Unknown market type - don't guess, don't crash
        return None

from rest_framework import serializers
from .models import Fixtures, Oddsnapshot, TeamForm, Prediction


class OddsnapshotSerializer(serializers.ModelSerializer):
    """
    Read-only - odds rows are written exclusively by the data-gatherer
    agent (OddsSnapshot.objects.create(...)), never through this serializer.
    `fixture` is intentionally excluded: this serializer is always nested
    inside a FixturesSerializer response, where the fixture is already known.
    """
    class Meta:
        model = Oddsnapshot
        fields = ['id', 'bookmaker', 'home_odds', 'draw_odds', 'away_odds', 'captured_at']
        read_only_fields = fields


class TeamFormSerializer(serializers.ModelSerializer):
    """
    Read-only - written exclusively by the Analyst agent's
    TeamForm.objects.update_or_create(...) call. `id` and `fixture` are
    excluded: nobody looks up a TeamForm row by its own ID, only ever in
    the context of "this team, in this fixture" (already implied by nesting).
    """
    class Meta:
        model = TeamForm
        fields = [
            'team_name', 'is_home_team',
            'wins_last_5', 'draws_last_5', 'losses_last_5',
            'goals_for_avg', 'goals_against_avg',
            'head_to_head_summary', 'injuries',
            'computed_at',
        ]
        read_only_fields = fields


class PredictionSerializer(serializers.ModelSerializer):
    """
    Read-only - written exclusively by the Predictor agent's
    Prediction.objects.create(...) call. `outcomes` is a JSONField and
    needs no special handling here - DRF passes the dict straight through,
    including the nested {"pick": ..., "was_correct": ...} shape inside
    each market entry.

    `id` IS included here (unlike TeamForm) because multiple Prediction
    rows can exist per fixture over time - the ID is how a client
    disambiguates "this specific historical prediction" from "the latest one."
    """
    class Meta:
        model = Prediction
        fields = ['id', 'outcomes', 'confidence', 'reasoning', 'model_used', 'created_at']
        read_only_fields = fields


class FixturesSerializer(serializers.ModelSerializer):
    """
    Top-level serializer combining a fixture with its latest odds, all
    current form stats, and its latest prediction.

    IMPORTANT: get_latest_odds() and get_latest_prediction() read from
    .all() on the related manager, NOT .order_by().first(). This only
    avoids N+1 queries if the calling view's queryset used Prefetch with
    matching ordering - see FixtureListView for the required pattern.
    Calling this serializer against an un-prefetched queryset still works
    correctly, just without the query-count benefit.
    """
    latest_odds = serializers.SerializerMethodField()
    form_stats = TeamFormSerializer(many=True, read_only=True)
    latest_prediction = serializers.SerializerMethodField()

    class Meta:
        model = Fixtures
        fields = [
            'id', 'sport', 'home_team', 'away_team', 'league',
            'kickoff_time', 'status', 'home_score', 'away_score',
            'latest_odds', 'form_stats', 'latest_prediction',
        ]
        read_only_fields = fields

    def get_latest_odds(self, obj):
        all_odds = list(obj.odds.all())
        return OddsnapshotSerializer(all_odds[0]).data if all_odds else None

    def get_latest_prediction(self, obj):
        all_predictions = list(obj.predictions.all())
        return PredictionSerializer(all_predictions[0]).data if all_predictions else None


class PredictionRequestSerializer(serializers.Serializer):
    """
    Validates incoming filter params for the prediction-generation endpoint.
    Not a ModelSerializer - this doesn't represent a model, just incoming
    query parameters the view needs validated before calling the coordinator.
    """
    sport = serializers.ChoiceField(choices=['football', 'basketball', 'tennis'])
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    force_refresh = serializers.BooleanField(required=False, default=False)
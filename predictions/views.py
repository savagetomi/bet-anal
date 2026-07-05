from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Fixtures, Oddsnapshot, Prediction
from .serializers import (
    FixturesSerializer,
    PredictionSerializer,
    PredictionRequestSerializer,
)
from .agents.coordinator import (
    get_predictions_for_sport,
    get_prediction_for_single_fixture,
)


class FixtureListView(APIView):
    """
    GET /api/predictions/fixtures/?sport=football&status=scheduled
    Cheap read-only endpoint. Returns fixtures with their latest
    pre-computed prediction nested in. No LLM calls here - just
    reads what the midnight job already stored.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List fixtures with their latest predictions",
        description=(
            "Returns upcoming fixtures for the given sport, each with its "
            "latest pre-computed prediction nested in. Predictions are "
            "generated daily at midnight - this endpoint only reads them."
        ),
        parameters=[
            OpenApiParameter(
                name='sport',
                description='Filter by sport: football, basketball, or tennis',
                required=True,
                type=str,
                enum=['football', 'basketball', 'tennis'],
            ),
            OpenApiParameter(
                name='status',
                description='Filter by fixture status',
                required=False,
                type=str,
                enum=['scheduled', 'live', 'finished', 'postponed'],
            ),
        ],
        responses={
            200: FixturesSerializer(many=True),
            400: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request):
        sport = request.query_params.get('sport')
        if not sport:
            return Response(
                {"error": "sport is required. Must be one of: football, basketball, tennis."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if sport not in ('football', 'basketball', 'tennis'):
            return Response(
                {"error": f"Invalid sport '{sport}'. Must be one of: football, basketball, tennis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = Fixtures.objects.filter(sport=sport).prefetch_related(
            Prefetch('odds', queryset=Oddsnapshot.objects.order_by('-captured_at')),
            Prefetch('predictions', queryset=Prediction.objects.order_by('-created_at')),
            'form_stats',
        ).order_by('kickoff_time')

        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        serializer = FixturesSerializer(queryset, many=True)
        return Response({
            "sport": sport,
            "count": queryset.count(),
            "results": serializer.data,
        }, status=status.HTTP_200_OK)


class FixtureDetailView(APIView):
    """
    GET /api/predictions/fixtures/<fixture_id>/
    Returns one specific fixture with its full prediction detail.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get a single fixture with its prediction",
        responses={
            200: FixturesSerializer(),
            404: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request, fixture_id):
        try:
            fixture = Fixtures.objects.prefetch_related(
                Prefetch('odds', queryset=Oddsnapshot.objects.order_by('-captured_at')),
                Prefetch('predictions', queryset=Prediction.objects.order_by('-created_at')),
                'form_stats',
            ).get(id=fixture_id)
        except Fixtures.DoesNotExist:
            return Response(
                {"error": "Fixture not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = FixturesSerializer(fixture)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GeneratePredictionsView(APIView):
    """
    POST /api/predictions/generate/
    Runs the full agent pipeline for all fixtures of a given sport.
    This is what the midnight scheduled job calls - not meant for
    regular users to trigger on demand.
    Consider restricting to IsAdminUser in production.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Generate predictions for a sport (admin/scheduled job use)",
        description=(
            "Triggers the full data-gather → analyze → predict pipeline "
            "for all upcoming fixtures of the given sport. Existing "
            "predictions are reused unless force_refresh=true. "
            "Intended for the midnight scheduled job, not end users."
        ),
        request=PredictionRequestSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            502: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request):
        params = PredictionRequestSerializer(data=request.data)
        if not params.is_valid():
            return Response(params.errors, status=status.HTTP_400_BAD_REQUEST)

        data = params.validated_data

        try:
            results = get_predictions_for_sport(
                sport=data['sport'],
                date_from=data.get('date_from'),
                date_to=data.get('date_to'),
                force_refresh=data.get('force_refresh', False),
            )
        except Exception as e:
            return Response(
                {"error": f"Pipeline failed: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY
            )

        successes = [r for r in results if "error" not in r]
        errors = [r for r in results if "error" in r]

        return Response({
            "sport": data['sport'],
            "total": len(results),
            "predictions_generated": len(successes),
            "errors": len(errors),
            "error_details": errors if errors else [],
            "results": successes,
        }, status=status.HTTP_200_OK)


class PredictionDetailView(APIView):
    """
    POST /api/predictions/fixture/<fixture_id>/predict/
    Force-generates or refreshes a prediction for one specific fixture.
    Returns existing prediction if one exists, unless force_refresh=true.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get or generate prediction for one fixture",
        parameters=[
            OpenApiParameter(
                name='force_refresh',
                description='If true, re-runs the pipeline even if a prediction exists',
                required=False,
                type=bool,
            ),
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            502: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request, fixture_id):
        force_refresh = request.data.get('force_refresh', False)

        try:
            result = get_prediction_for_single_fixture(
                fixture_id=str(fixture_id),
                force_refresh=force_refresh,
            )
        except Fixtures.DoesNotExist:
            return Response(
                {"error": "Fixture not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except RuntimeError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Prediction failed: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY
            )

        return Response(result, status=status.HTTP_200_OK)

from django.urls import path
from .views import (
    FixtureListView,
    FixtureDetailView,
    GeneratePredictionsView,
    PredictionDetailView,
)

urlpatterns = [
    # Read endpoints - what users hit
    path('fixtures/', FixtureListView.as_view(), name='fixture-list'),
    path('fixtures/<uuid:fixture_id>/', FixtureDetailView.as_view(), name='fixture-detail'),

    # Pipeline endpoints - what the midnight job hits
    path('generate/', GeneratePredictionsView.as_view(), name='generate-predictions'),
    path('fixture/<uuid:fixture_id>/predict/', PredictionDetailView.as_view(), name='prediction-detail'),
]
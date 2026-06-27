from django.urls import path
from .views import (
    UserProfileView, RegisterUser,
    CreateBetView, LoginUserView, ViewBetDetails, ViewIndividualBetDetails, RolloverCalculator, BetAnalysisViews, UpdateBetView
)

urlpatterns = [
    path('register/', RegisterUser.as_view(), name='user-register'),
    path('login/', LoginUserView.as_view(), name='user-login'),
    path('profile/<uuid:pk>/', UserProfileView.as_view(), name='user-profile'),
    # path('sync-bets/', SyncBetsView.as_view(), name='sync-bets'),
    path('create/', CreateBetView.as_view(), name='bet-create'),
    path('update/<uuid:bet_id>/', UpdateBetView.as_view(), name='bet-update'),
    path('view-bets/', ViewBetDetails.as_view(), name='user-bets'),
    path('view-bets/<uuid:bet_id>/', ViewIndividualBetDetails.as_view(), name='bet-details'), 
    path('rollover/', RolloverCalculator.as_view(), name='rollover-calculator'),
    path('analysis/', BetAnalysisViews.as_view(), name='bet-analysis'),
    ]

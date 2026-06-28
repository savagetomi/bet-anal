from django.contrib.auth import authenticate, login
from django.db import models
from .serializers import CreateBetSerializer, UserSerializer
from .models import Bet
from django.db.models import DecimalField, Sum, Count, Q, F, Value, CharField, When, Case
# from .services import StakeDataClient
from rest_framework import generics, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.types import OpenApiTypes
import os
import math


# Create your views here.

class RegisterUser(APIView):
    @extend_schema(
    summary="Register a new user",
    description="Creates a new user account and returns the created user's profile data.",
    request=UserSerializer,
    responses={
        201: inline_serializer(
            name="RegisterUserResponse",
            fields={
                "message": serializers.CharField(),
                "data": inline_serializer(
                    name="RegisterUserData",
                    fields={
                        "id": serializers.IntegerField(),
                        "email": serializers.EmailField(),
                        "first_name": serializers.CharField(),
                        "last_name": serializers.CharField(),
                        "username": serializers.CharField(),
                        "created_at": serializers.DateTimeField(),
                        "updated_at": serializers.DateTimeField(),
                    }
                ),
            }
        ),
        400: OpenApiTypes.OBJECT,
    },
)
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": 'User created successfully',
                    "data": {
                        "id": user.id,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "username": user.username,
                        "created_at": user.created_at,
                        "updated_at": user.updated_at
                    }
                }
                , status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginUserView(APIView):
    @extend_schema(
    summary="Log in a user",
    description="Authenticates a user with username and password, returning JWT access and refresh tokens.",
    request=inline_serializer(
        name="LoginRequest",
        fields={
            "username": serializers.CharField(),
            "password": serializers.CharField(style={'input_type': 'password'}),
        }
    ),
    responses={
        200: inline_serializer(
            name="LoginResponse",
            fields={
                "message": serializers.CharField(),
                "access": serializers.CharField(),
                "refresh": serializers.CharField(),
                "data": UserSerializer(),
            }
        ),
        401: OpenApiTypes.OBJECT,
    },
)
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
            access = AccessToken.for_user(user)
            refresh = RefreshToken.for_user(user)

            login(request, user)
            serializer = UserSerializer(user)
            return Response({
                "message": "Login successful",
                "access": str(access),
                "refresh": str(refresh),
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
    summary="Get the authenticated user's profile",
    responses={200: inline_serializer(
        name="UserProfileResponse",
        fields={"message": serializers.CharField(), "data": UserSerializer()}
    )},
)
    def get(self, request, pk):
        try:
            serializer = UserSerializer(request.user)
            return Response({
                "message": "User profile retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

# class SyncBetsView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         token = os.environ.get('STAKE_API_TOKEN')
#         if not token:
#             return Response({'error': 'API token not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
#         client = StakeDataClient(api_token=token)
#         try:
#             bets_data = client.get_bet_history()
            
#             # Assuming bets_data is a list of dictionaries
#             for bet in bets_data:
#                 BetAnalysis.objects.update_or_create(
#                     bet_id=bet['id'],
#                     defaults={
#                         'user': request.user,
#                         'amount': bet['amount'],
#                         'payout': bet.get('payout'),
#                         'game_name': bet['game_name'],
#                         'game_type': bet['game_type'],
#                         'created_at': bet['created_at']
#                     }
#                 )
#             return Response({'message': 'Bets synced successfully'}, status=status.HTTP_200_OK)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CreateBetView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="Create a new bet",
        description="Creates a bet for the authenticated user. `user` is set automatically from the request and cannot be supplied by the client.",
        request=CreateBetSerializer,
        responses={
            201: inline_serializer(
                name="CreateBetResponse",
                fields={
                    "message": serializers.CharField(),
                    "data": inline_serializer(
                        name="CreateBetData",
                        fields={
                            "id": serializers.IntegerField(),
                            "bet_id": serializers.UUIDField(),
                            "stake": serializers.DecimalField(max_digits=10, decimal_places=2),
                            "potential_payout": serializers.DecimalField(max_digits=10, decimal_places=2),
                            "game_type": serializers.CharField(),
                            "number_of_games": serializers.IntegerField(),
                            "created_at": serializers.DateTimeField(),
                            "result": serializers.CharField(),
                        }
                    ),
                }
            ),
            400: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request):
        user = request.user
        serializer = CreateBetSerializer(data=request.data)
        if serializer.is_valid():
            bet = serializer.save(user=user)
            return Response({
                "message": "Bet created successfully",
                "data": {
                    "id": bet.id,
                    "bet_id": bet.bet_id,
                    "stake": bet.stake,
                    "potential_payout": bet.potential_payout,
                    "game_type": bet.game_type,
                    "number_of_games": bet.number_of_games,
                    "created_at": bet.created_at,
                    "result": bet.result
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class UpdateBetView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="Update an existing bet",
        description=(
            "Partially updates a bet belonging to the authenticated user, identified by bet_id. "
            "Note: CreateBetSerializer marks `result` as read-only, so this endpoint currently "
            "cannot change a bet's result - only fields like stake, game_type, etc. are writable."
        ),
        request=CreateBetSerializer,
        responses={
            200: inline_serializer(
                name="UpdateBetResponse",
                fields={
                    "message": serializers.CharField(),
                    "data": CreateBetSerializer(),
                }
            ),
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def put(self, request, bet_id):
        try:
            bet = Bet.objects.get(bet_id=bet_id, user=request.user)
        except Bet.DoesNotExist:
            return Response({'error': 'Bet not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CreateBetSerializer(bet, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Bet updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class ViewBetDetails(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="List all bets for the authenticated user",
        responses={
            200: inline_serializer(
                name="ViewBetDetailsResponse",
                fields={
                    "message": serializers.CharField(),
                    "data": CreateBetSerializer(many=True),
                }
            ),
        },
    )
    def get(self, request):
        try:
            bet = Bet.objects.filter(user=request.user)
            serializer = CreateBetSerializer(bet, many=True)
            return Response({
                "message": "Bet details retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Bet.DoesNotExist:
            return Response({'error': 'Bet not found'}, status=status.HTTP_404_NOT_FOUND)
        
class ViewIndividualBetDetails(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="Get a single bet by bet_id",
        responses={
            200: inline_serializer(
                name="ViewIndividualBetDetailsResponse",
                fields={
                    "message": serializers.CharField(),
                    "data": CreateBetSerializer(),
                }
            ),
            404: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request, bet_id):
        try:
            bet = Bet.objects.get(bet_id=bet_id, user=request.user)
            serializer = CreateBetSerializer(bet)
            return Response({
                "message": "Bet details retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Bet.DoesNotExist:
            return Response({'error': 'Bet not found'}, status=status.HTTP_404_NOT_FOUND)

class BetAnalysisViews(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
    summary="Get aggregated profit/loss analysis",
    description=(
        "Returns aggregated betting statistics for the authenticated user: "
        "total bets, win/loss/pending counts, total amount staked, and net "
        "profit/loss. Pending bets contribute 0 to profit/loss but their "
        "stake is still included in total_staked."
    ),
    responses={200: inline_serializer(
        name="BetAnalysisResponse",
        fields={
            "message": serializers.CharField(),
            "data": inline_serializer(
                name="BetAnalysisData",
                fields={
                    "total_bets": serializers.IntegerField(),
                    "won_bets": serializers.IntegerField(),
                    "lost_bets": serializers.IntegerField(),
                    "pending_bets": serializers.IntegerField(),
                    "total_profit_loss": serializers.DecimalField(max_digits=10, decimal_places=2),
                    "total_staked": serializers.DecimalField(max_digits=10, decimal_places=2),
                }
            ),
        }
    )},
)
    def get(self, request):
        bets= Bet.objects.filter(user=request.user)
        bets=bets.annotate(
            calulated_pl = Case(
                When(result='won', then=F('potential_payout') - F('stake')),
                When(result='lost', then= 0 -F('stake')),
                When(result='pending', then=0),
                default=0,
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )
        total = bets.aggregate(
            total_profit_loss=Sum('calulated_pl'),
            total_staked = Sum('stake'),
            total_bets=Count('id'),
            won_bets=Count('id', filter=Q(result='won')),
            lost_bets=Count('id', filter=Q(result='lost')),
            pending_bets=Count('id', filter=Q(result='pending')),
        )
        # counts = bets.aggregate(
        #     total_bets=Count('id'),
        #     won_bets=Count('id', filter=models.Q(result='won')),
        #     lost_bets=Count('id', filter=models.Q(result='lost')),
        #     pending_bets=Count('id', filter=models.Q(result='pending')),
        # )
        # total_staked = bets.aggregate(total_staked=Sum('stake'))['total_staked'] or 0
        return Response({
            "message": "Bet analysis retrieved successfully",
            "data": {
                "total_bets": total['total_bets'],
                "won_bets": total['won_bets'],
                "lost_bets": total['lost_bets'],
                "pending_bets": total['pending_bets'],
                "total_profit_loss": total['total_profit_loss'] or 0,
                "total_staked": total['total_staked']
            }
        }, status=status.HTTP_200_OK) 

        
class RolloverCalculator(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
    summary="Calculate rollover requirement",
    description=(
        "Given a stake, a potential payout, and a number of days, calculates "
        "the overall rollover multiplier and the equivalent required daily "
        "rollover rate (geometric average)."
    ),
    request=inline_serializer(
        name="RolloverRequest",
        fields={
            "stake": serializers.FloatField(),
            "payout": serializers.FloatField(),
            "days": serializers.IntegerField(),
        }
    ),
    responses={
        200: inline_serializer(
            name="RolloverResponse",
            fields={
                "message": serializers.CharField(),
                "data": inline_serializer(
                    name="RolloverData",
                    fields={
                        "stake": serializers.FloatField(),
                        "payout": serializers.FloatField(),
                        "rollover_requirement": serializers.FloatField(),
                        "daily_rollover": serializers.FloatField(),
                    }
                ),
            }
        ),
        400: OpenApiTypes.OBJECT,
    },
)
    def post(self, request):
        stake = request.data.get('stake')
        payout = request.data.get('payout')
        days = request.data.get('days')  # Default to 30 days if not provided

        if stake is None :
            return Response({'error': 'Stake  are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if payout is None:
            return Response({'error': 'Potential payout is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if days is None:
            return Response({'error': 'Number of days is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            stake = float(stake)
            payout = float(payout)
        except ValueError:
            return Response({'error': 'Stake and payout must be numbers.'}, status=status.HTTP_400_BAD_REQUEST)

        if stake <= 0 or payout <= 0:
            return Response({'error': 'Stake and payout must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)

        rollover_requirement = (payout - stake) / stake
        daily_rollover = rollover_requirement ** (1 / int(days))
        rounded = round(daily_rollover, 2)

        return Response({
            "message": "Rollover requirement calculated successfully",
            "data": {
                "stake": stake,
                "payout": payout,
                "rollover_requirement": rollover_requirement,
                "daily_rollover": rounded,
            }
        }, status=status.HTTP_200_OK)
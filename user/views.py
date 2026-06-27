from django.contrib.auth import authenticate, login
from django.db import models
from .serializers import CreateBetSerializer, UserSerializer
from .models import Bet
from django.db.models import DecimalField, Sum, Count, Q, F, Value, CharField, When, Case
# from .services import StakeDataClient
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
import os
import math

# Create your views here.
class RegisterUser(APIView):
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
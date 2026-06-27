from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from .models import CustomUser, Bet

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'password', 'username', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user


class CreateBetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bet
        fields = ['id', 'bet_id', 'stake', 'potential_payout', 'game_type', 'number_of_games', 'result','profit_loss']
        read_only_fields = ['id', 'bet_id', 'created_at']

    def validate_stake(self, value):
        if value < 100:
            raise serializers.ValidationError("Stake cannot be less than 100NGN.")
        return value

    def create(self, validated_data):
        return Bet.objects.create(**validated_data)
    
    def profit_loss(self, obj):
        if obj.result == "pending":
            return "Bet is Pending"
        return obj.profit_loss()

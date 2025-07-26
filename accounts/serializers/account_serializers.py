from datetime import date, datetime, timedelta
import re
from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
from utils.utils import to_aware_datetime
from accounts.models import GymMember, GymPackage


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError("Both email and password are required.")
        
        return attrs
    
class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    
    def validate(self, attrs):
        refresh = attrs.get('refresh')
        
        if not refresh:
            raise serializers.ValidationError("Refresh token is required.")
        # validate token is not expired
        try:
            token = RefreshToken(refresh)
            if token.is_expired():
                raise serializers.ValidationError("Refresh token is expired.")
        except Exception as e:
            raise serializers.ValidationError(f"Invalid refresh token: {str(e)}")
        
        return attrs
    



class TokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField()

class LoginResponseSerializer(serializers.Serializer):
    jwt_token = serializers.CharField()
    refresh = serializers.CharField()
    user = serializers.CharField()
    tenant_id = serializers.CharField()
    subdomain = serializers.CharField()
    jwt_expires_at = serializers.DateTimeField()
    refresh_expires_at = serializers.DateTimeField()


class DashboardActiveMemberSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    check_in = serializers.CharField(allow_null=True)
    check_out = serializers.CharField(allow_null=True)
    payment_due_date = serializers.CharField(allow_null=True)

class DashboardResponseSerializer(serializers.Serializer):
    Revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    Members = serializers.IntegerField()
    active_members = DashboardActiveMemberSerializer(many=True)
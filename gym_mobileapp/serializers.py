from datetime import date, datetime, timedelta
import re
from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
from utils.utils import to_aware_datetime
from django.utils import timezone
from rest_framework import serializers
from gymowners.models import  GymUserOtherInfo, CustomUser , GymTrainerOtherInfo
from accounts.models import Attendance, Client
from accounts.models import LoginSession, Attendance
from rest_framework import status


class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = ['id', 'punch_in_time', 'punch_out_time', 'latitude', 'longitude', 'year', 'week_of_year']
        read_only_fields = ['id', 'punch_in_time', 'punch_out_time']
    
    def validate(self, attrs):
        user = self.context['request'].user
        if not user.is_authenticated:
            raise serializers.ValidationError("User is not authenticated.", code=status.HTTP_401_UNAUTHORIZED)
        
        if 'punch_in_time' in attrs and 'punch_out_time' in attrs:
            if attrs['punch_in_time'] >= attrs['punch_out_time']:
                raise serializers.ValidationError("Punch-in time must be before punch-out time.", code=status.HTTP_400_BAD_REQUEST)
        
        return attrs


class PunchOutSerializer(serializers.Serializer):
    def validate(self, attrs):
        with schema_context(settings.PUBLIC_SCHEMA_NAME):
            user_model = get_user_model()
            user = user_model.objects.get(id=self.context['request'].user.id, is_active=True, role=settings.ROLE_GYM_USER)
        if not user:
            raise serializers.ValidationError("User not found or inactive.", code=status.HTTP_404_NOT_FOUND)
        attendance = Attendance.objects.filter(
            user=user.id,
            punch_out_time__isnull=True
        ).order_by('-punch_in_time').first()
        if not attendance:
            raise serializers.ValidationError("No active punch in found.", code=status.HTTP_404_NOT_FOUND)
        return attrs

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError("Both email and password are required.", code=status.HTTP_400_BAD_REQUEST)

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
                raise serializers.ValidationError("Refresh token is expired.", code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            raise serializers.ValidationError(f"Invalid refresh token: {str(e)}", code=status.HTTP_400_BAD_REQUEST)

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

class PasswordUpdateSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        if len(value) < 6:
            raise serializers.ValidationError("Password must be at least 6 characters long.", code= status.HTTP_400_BAD_REQUEST)
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.", code= status.HTTP_400_BAD_REQUEST)
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.", code= status.HTTP_400_BAD_REQUEST)
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("Password must contain at least one digit.", code= status.HTTP_400_BAD_REQUEST)
        if not re.search(r'[@$!%*?&]', value):
            raise serializers.ValidationError("Password must contain at least one special character.", code= status.HTTP_400_BAD_REQUEST)
        if re.search(r'\s', value):
            raise serializers.ValidationError("Password must not contain any spaces.", code= status.HTTP_400_BAD_REQUEST)
        user = self.context['request'].user
        if user.check_password(value):
            raise serializers.ValidationError("New password cannot be the same as the old password.", code= status.HTTP_400_BAD_REQUEST)

        return value
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    

class GymUserOtherInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = GymUserOtherInfo
        # list all the fields you want exposed
        fields = [
            'emergency_contact_number',
            'address',
            'batch',
            'height',
            'weight',
            'blood_group',
            'medical_conditions',
            'fitness_goals',
            'notes',
            'attachments',
            'date_of_birth',
            'gender',
            'is_active',
        ]

class UserDetailSerializer(serializers.ModelSerializer):
    other_info = GymUserOtherInfoSerializer(source='gymuserotherinfo', read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'first_name',
            'middle_name',
            'last_name',
            'email',
            'phone_number',
            'role',
            'created_on',
            'updated_on',
            'other_info',
        ]
        read_only_fields = fields

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            'gym_name',
            'gym_uuid',
            'gym_location',
            'gym_phone_number',
            'gym_email',
            'latitude',
            'longitude',
            'is_active',
            'ratings',
            'created_on',
            'updated_on'
        ]
        read_only_fields = ['gym_uuid', 'created_on', 'updated_on']


class GymTrainerOtherInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = GymTrainerOtherInfo
        fields = [
            'past_experience',
            'specialization',
            'certifications',
            'medical_conditions',
            'blood_group',
            'address',
            'date_of_birth',
            'gender',
            'is_active'
                            ]
        read_only_fields = ['is_active']


class TrainerSerializer(serializers.ModelSerializer):
    other_info = GymTrainerOtherInfoSerializer(source='gymtrainerotherinfo', read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'first_name',
            'middle_name',
            'last_name',
            'email',
            'phone_number',
            'role',
            'created_on',
            'updated_on',
            'other_info',
        ]
        read_only_fields = fields
from rest_framework import serializers
from gymowners.models import Client
from accounts.models import GymPackage
from django.contrib.auth.models import User
from datetime import date, timedelta
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
import re

class GymOwnerRegistrationSerializer(serializers.Serializer):
    gym_email = serializers.EmailField()
    gym_name = serializers.CharField(max_length=100, required=True, allow_blank=False)
    gym_location = serializers.CharField(max_length=100, required=False, allow_blank=True)
    gym_phone_number = serializers.CharField(max_length=15, required=False, allow_blank=True)
    gym_owner_email = serializers.EmailField(required=True, allow_blank=False)
    gym_owner_password = serializers.CharField(write_only=True, min_length=6)
    gym_owner_name = serializers.CharField(max_length=100)
    gym_owner_phone_number = serializers.CharField(max_length=15, required=False, allow_blank=True)
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    

    # validate longitude and latitude
    def validate_latitude(self, value):
        if value is not None and (value < -90 or value > 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90 degrees.")
        return value
    def validate_longitude(self, value):
        if value is not None and (value < -180 or value > 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180 degrees.")
        return value

    def validate_gym_email(self, value):
        if Client.objects.filter(gym_email__iexact=value).exists():
            raise serializers.ValidationError("A gym with this email already exists.")
        return value
    
    def validate_gym_name(self, value):
        value = re.sub(r'[^a-zA-Z0-9\s]', '', value)
        value = re.sub(r'\s+', ' ', value).strip()
        if Client.objects.filter(gym_name__iexact=value).exists():
            raise serializers.ValidationError("A gym with this name already exists.")
        # Clean the name to remove special characters and spaces
        if not value:
            raise serializers.ValidationError("Gym name cannot be empty or contain only special characters.")
        if len(value) > 100:
            raise serializers.ValidationError("Gym name cannot exceed 100 characters.")
        if value[0].isdigit():
            raise serializers.ValidationError("Gym name cannot start with a digit.")
        if not value[0].isalpha():
            raise serializers.ValidationError("Gym name must start with an alphabetic character.")
        if not value.isalnum() and ' ' not in value:
            raise serializers.ValidationError("Gym name can only contain alphanumeric characters and spaces.")
        if not value.isascii():
            raise serializers.ValidationError("Gym name can only contain ASCII characters.")
        # Make first letter of each word capital and other letters lowercase
        return ' '.join([word.capitalize() for word in value.split()])
    
    def validate_gym_phone_number(self, value):
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Phone number must be between 9 and 15 digits long and can start with a '+' sign.")
        return value
    
    def validate_gym_owner_email(self, value):
        with schema_context(settings.PUBLIC_SCHEMA_NAME):
            user_model = get_user_model()
            user = user_model.objects.filter(email=value)
        if user.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_gym_owner_password(self, value):
        if len(value) < 6:
            raise serializers.ValidationError("Password must be at least 6 characters long.")
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("Password must contain at least one digit.")
        if not re.search(r'[@$!%*?&]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        if re.search(r'\s', value):
            raise serializers.ValidationError("Password must not contain any spaces.")
        return value
    
    def validate_gym_owner_name(self, value):
        # Clean the name to remove special characters and spaces
        value = re.sub(r'[^a-zA-Z\s]', '', value)
        value = re.sub(r'\s+', ' ', value).strip()
        if not value:
            raise serializers.ValidationError("Gym owner's name cannot be empty or contain only special characters.")
        if len(value) > 100:
            raise serializers.ValidationError("Gym owner's name cannot exceed 100 characters.")
        if value[0].isdigit():
            raise serializers.ValidationError("Gym owner's name cannot start with a digit.")
        if not value[0].isalpha():
            raise serializers.ValidationError("Gym owner's name must start with an alphabetic character.")
        if not value.isascii():
            raise serializers.ValidationError("Gym owner's name can only contain ASCII characters.")
        # Make first letter of each word capital and other letters lowercase
        return ' '.join([word.capitalize() for word in value.split()])
    
    def validate_gym_owner_phone_number(self, value):
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Phone number must be between 9 and 15 digits long and can start with a '+' sign.")
        return value

class PasswordUpdateSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


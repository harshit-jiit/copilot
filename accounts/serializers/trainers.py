
from datetime import date, datetime, timedelta
from rest_framework import serializers
from django_tenants.utils import schema_context
from django.conf import settings
from django.contrib.auth import get_user_model
from gymowners.models import Client
import re

class AddGymTrainer(serializers.Serializer):
    first_name = serializers.CharField(max_length=50, required=True)
    last_name = serializers.CharField(max_length=50, required=True)
    middle_name = serializers.CharField(max_length=50, required=False)
    email = serializers.EmailField(required=True)
    phone_number = serializers.CharField(max_length=20, required=True)
    emergency_contact_number = serializers.CharField(max_length=20, required=True)
    date_of_birth = serializers.DateField(required=True)
    gender = serializers.CharField(max_length=10, required=True)
    address = serializers.CharField(max_length=200, required=True)
    blood_group = serializers.CharField(max_length=10, required=True)
    medical_condition = serializers.CharField(max_length=200, required=False)
    past_experience = serializers.CharField(max_length=200, required=False)
    certifications = serializers.CharField(max_length=200, required=False)
    specializations = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=True,
        help_text="List of activity IDs associated with this package"
    )


    def validate_email(self, value):
        with schema_context(settings.PUBLIC_SCHEMA_NAME):
            if Client.objects.filter(gym_email__iexact=value).exists():
                raise serializers.ValidationError("A gym with this email already exists.")
            user_model = get_user_model()
            if user_model.objects.filter(email__iexact=value).exists():
                raise serializers.ValidationError("A user with this email already exists.")

            if user_model.objects.filter(username__iexact=value).exists():
                raise serializers.ValidationError("A user with this username already exists.")

        return value
    
    def validate_phone_number(self, value):
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Phone number must be between 9 and 15 digits long and can start with a '+' sign.")
        with schema_context(settings.PUBLIC_SCHEMA_NAME):
            if get_user_model().objects.filter(phone_number__iexact=value).exists():
                raise serializers.ValidationError("A user with this phone number already exists.")
            if Client.objects.filter(gym_phone_number__iexact=value).exists():
                raise serializers.ValidationError("A gym with this phone number already exists.")
        return value

    def validate_emergency_contact_number(self, value):
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Phone number must be between 9 and 15 digits long and can start with a '+' sign.")
        return value

    def validate_gender(self, value):
        if value not in ['Male', 'Female', 'Other']:
            raise serializers.ValidationError("Invalid gender. Please choose from Male, Female or Other.")
        return value
    
    def validate_blood_group(self, value):
        if value not in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
            raise serializers.ValidationError("Invalid blood group. Please choose from A+, A-, B+, B-, AB+, AB-, O+, O-")
        return value
    
    def validate_date_of_birth(self, value):
        if value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        # maximum age limit is 60 years
        if value < date.today() - timedelta(days=60*365):
            raise serializers.ValidationError("Date of birth cannot be more than 60 years ago.")
        # minimum age limit is 18 years
        if value > date.today() - timedelta(days=18*365):
            raise serializers.ValidationError("Date of birth cannot be less than 18 years ago.")
        return value

    def validate_specializations(self, value):
        valid_keys = [choice[0] for choice in settings.SPECIALIZATION_CHOICES]
        if not all(item in valid_keys for item in value):
            raise serializers.ValidationError(
                f"Invalid specialization. Please choose from the available options {valid_keys}"
            )
        return value

class ActiveGymTrainerSerializer(serializers.Serializer):
    trainer_id = serializers.IntegerField()
    first_name = serializers.CharField(max_length=50, required=True)
    last_name = serializers.CharField(max_length=50, required=True)
    middle_name = serializers.CharField(max_length=50, required=False)
    email = serializers.EmailField(required=True)
    phone_number = serializers.CharField(max_length=20, required=True)
    emergency_contact_number = serializers.CharField(max_length=20, required=True)
    date_of_birth = serializers.DateField(required=True)
    gender = serializers.CharField(max_length=10, required=True)
    address = serializers.CharField(max_length=200, required=True)
    blood_group = serializers.CharField(max_length=10, required=True)
    medical_condition = serializers.CharField(max_length=200, required=False)
    past_experience = serializers.CharField(max_length=200, required=False)
    certifications = serializers.CharField(max_length=200, required=False)
    specializaations = serializers.CharField(max_length=200, required=False)
    

class AddGymTrainerResponse(serializers.Serializer):
    detail = serializers.CharField()
    trainer = ActiveGymTrainerSerializer()
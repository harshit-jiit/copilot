from datetime import date, datetime, timedelta
from rest_framework import serializers
from django_tenants.utils import schema_context
from django.conf import settings
from django.contrib.auth import get_user_model
from gymowners.models import Client
import re
from accounts.models import GymMember, GymPackage, GymActivity
from datetime import date, datetime, timedelta
from utils.utils import to_aware_datetime
import imghdr
from gymowners.models import GymTrainerOtherInfo
from django.db import connection

class AddGymMemberSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=50, required=True)
    last_name = serializers.CharField(max_length=50, required=True)
    middle_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    phone_number = serializers.CharField(max_length=20, required=True)
    emergency_contact_number = serializers.CharField(max_length=20, required=True)
    date_of_birth = serializers.DateField(required=True)
    gender = serializers.CharField(max_length=10, required=True)
    address = serializers.CharField(max_length=200, required=True)
    blood_group = serializers.CharField(max_length=10, required=True)
    height = serializers.DecimalField(max_digits=5, decimal_places=2, required=True)
    weight = serializers.DecimalField(max_digits=5, decimal_places=2, required=True)   
    batch = serializers.CharField(max_length=20, required=True)
    medical_conditions = serializers.CharField(max_length=200, required=False, allow_blank=True)
    fitness_goals = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[],
        allow_empty=True,
        help_text="List of fitness goals associated with this member"
    )
    notes = serializers.CharField(max_length=200, required=False, allow_blank=True)
    attachments = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True,
        help_text="List of file attachments for the member"
    )
    trainer_id = serializers.IntegerField(required=True)
    membership_start_date = serializers.DateField(required=True)
    membership_end_date = serializers.DateField(required=False, allow_null=True)
    package_id = serializers.IntegerField(required=False, allow_null=True)
    referred_by = serializers.IntegerField(required=False, allow_null=True)
    activity_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="List of activity IDs associated with this member"
    )

    def validate_email(self, value):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise serializers.ValidationError("Invalid email format.")
        with schema_context(settings.PUBLIC_SCHEMA_NAME):
            user_model = get_user_model()
            if user_model.objects.filter(email=value).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate_phone_number(self, value):
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Phone number must be between 9 and 15 digits long and can start with a '+' sign.")
        with schema_context(settings.PUBLIC_SCHEMA_NAME):
            user_model = get_user_model()
            if user_model.objects.filter(phone_number=value).exists():
                raise serializers.ValidationError("A user with this phone number already exists.")
        return value
    
    def validate_membership_start_date(self, value):
        if value > date.today() + timedelta(days=90):
            raise serializers.ValidationError("Membership start date cannot be more ಮore than 90 days in the future.")
        if value < date.today() - timedelta(days=90):
            raise serializers.ValidationError("Membership start date cannot be in the past.")
        if self.initial_data.get('membership_end_date') and value > datetime.strptime(self.initial_data.get('membership_end_date'), "%Y-%m-%d").date():
            raise serializers.ValidationError("Membership start date cannot be after the end date.")
        return to_aware_datetime(value)
    
    def validate_membership_end_date(self, value):
        if not value:
            return None 
        if value and value < date.today():
            raise serializers.ValidationError("Membership end date cannot be in the past.")
        start_date_str = self.initial_data.get('membership_start_date')
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                raise serializers.ValidationError("Invalid format for membership start date.")
            if value < start_date:
                raise serializers.ValidationError("Membership end date cannot be before the start date.")
            if (value - start_date).days > 365:
                raise serializers.ValidationError("Membership duration cannot exceed 365 days.")
        return to_aware_datetime(value) if value else None
    
    def validate_package_id(self, value):
        if value is not None:
            package = GymPackage.objects.filter(id=value).first()
            if not package:
                raise serializers.ValidationError("Package with this ID does not exist.")
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
        if value < date.today() - timedelta(days=100*365):
            raise serializers.ValidationError("Date of birth cannot be more than 100 years ago.")
        if value > date.today() - timedelta(days=1*365):
            raise serializers.ValidationError("Date of birth cannot be less than 1 year ago.")
        return value

    def validate_height(self, value):
        if value > 250:
            raise serializers.ValidationError("Height cannot be more than 250 cm.")
        return value
    
    def validate_weight(self, value):
        if value > 250:
            raise serializers.ValidationError("Weight cannot be more than 250 kg.")
        return value
    
    def validate_batch(self, value):
        if value not in [i[0] for i in settings.BATCH_CHOICES]:
            raise serializers.ValidationError("Invalid batch. Please choose from the available batches. " \
                "Available batches: " + ", ".join(i[0] for i in settings.BATCH_CHOICES))
        return value
    
    def validate_fitness_goals(self, value):
        valid_goals = [i[0] for i in settings.GOAL_CHOICES]
        for goal in value:
            if goal not in valid_goals:
                raise serializers.ValidationError(f"Invalid fitness goal: {goal}. " \
                    f"Please choose from the available goals: {', '.join(valid_goals)}")
        return value

    def validate_attachments(self, files):
        allowed_types = ['jpeg', 'png', 'pdf', 'jpg']
        max_file_size = 5 * 1024 * 1024  # 5 MB
        for file in files:
            if file.size > max_file_size:
                raise serializers.ValidationError(f"{file.name}: File size should not exceed 5MB.")
            if not file.name:
                raise serializers.ValidationError(f"One of the files is missing a filename.")
            ext = file.name.split('.')[-1].lower()
            if ext not in allowed_types:
                raise serializers.ValidationError(f"{file.name}: Unsupported file type '.{ext}'. Allowed types: {', '.join(allowed_types)}")
            if ext in ['jpeg', 'jpg', 'png']:
                try:
                    if imghdr.what(file) is None:
                        raise serializers.ValidationError(f"{file.name}: Not a valid image file.")
                except Exception:
                    raise serializers.ValidationError(f"{file.name}: Corrupted or unreadable image.")
        return files
    
    def validate_trainer_id(self, value):
        tenant_schema = connection.tenant.schema_name
        with schema_context(settings.PUBLIC_SCHEMA_NAME):
            user_model = get_user_model()
            if not user_model.objects.filter(id=value, is_active=True, role=settings.ROLE_GYM_TRAINER).exists():
                raise serializers.ValidationError("Invalid trainer ID.")
            gym_trainer_info = GymTrainerOtherInfo.objects.filter(user=value).first()
            if not gym_trainer_info:
                raise serializers.ValidationError("Trainer information not found.")
            if tenant_schema != gym_trainer_info.current_gym.schema_name:
                raise serializers.ValidationError("Trainer does not belong to this gym.")
        return value

    def validate_referred_by(self, value):
        if value is not None:
            with schema_context(settings.PUBLIC_SCHEMA_NAME):
                user_model = get_user_model()
                if not user_model.objects.filter(id=value, is_active=True, role=settings.ROLE_GYM_USER).exists():
                    raise serializers.ValidationError("Invalid member ID.")
                if not user_model.objects.filter(id=value, is_active=True, role=settings.ROLE_GYM_TRAINER).exists():
                    raise serializers.ValidationError("Invalid trainer ID.")
        return value
    
    def validate_activity_ids(self, value):
        if value:
            for activity_id in value:
                if not GymActivity.objects.filter(id=activity_id, is_active=True).exists():
                    raise serializers.ValidationError("Invalid activity ID.")
        return value
            
    def validate(self, data):
        if data.get('package_id'):
            if data.get('membership_end_date') or data.get('activity_ids'):
                raise serializers.ValidationError(
                    "If package_id is provided, do not provide membership_end_date or activity_ids."
                )
        else:
            if not data.get('membership_end_date') or not data.get('activity_ids'):
                raise serializers.ValidationError(
                    "If package_id is not provided, both membership_end_date and activity_ids are required."
                )

        if data.get("membership_end_date") is None and data.get("package_id") is not None:
            package_duration = GymPackage.objects.filter(id=data['package_id']).first()
            data["membership_end_date"] = data["membership_start_date"] + timedelta(days=package_duration.package_duration) if package_duration else None

        return data

class ActiveGymMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    middle_name = serializers.CharField(allow_blank=True, required=False)
    phone_number = serializers.CharField(allow_blank=True, required=False)
    emergency_contact_number = serializers.CharField(allow_blank=True, required=False)
    date_of_birth = serializers.DateField(allow_null=True, required=False)
    gender = serializers.CharField(allow_blank=True, required=False)
    address = serializers.CharField(allow_blank=True, required=False)
    blood_group = serializers.CharField(allow_blank=True, required=False)
    height = serializers.FloatField(allow_null=True, required=False)
    weight = serializers.FloatField(allow_null=True, required=False)
    batch = serializers.CharField(allow_blank=True, required=False)
    medical_conditions = serializers.CharField(allow_blank=True, required=False)
    fitness_goals = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False
    )
    notes = serializers.CharField(allow_blank=True, required=False)
    attachments = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        ),
        allow_empty=True,
        required=False      
    )
    membership_start_date = serializers.DateTimeField()
    membership_end_date = serializers.DateTimeField()
    membership_status = serializers.CharField()
    package_id = serializers.IntegerField(allow_null=True, required=False)
    package_name = serializers.CharField(allow_blank=True, required=False)
    referred_by = serializers.CharField(allow_blank=True, required=False)
    custom_activity_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
        required=False
    )
    trainer_id = serializers.IntegerField(allow_null=True, required=False)
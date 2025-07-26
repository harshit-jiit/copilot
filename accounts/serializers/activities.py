
from datetime import date, datetime, timedelta
import re
from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
from utils.utils import to_aware_datetime
from accounts.models import GymMember, GymPackage, GymActivityType,GymActivity,GymActivityAssignedTrainer
from django.core.exceptions import ValidationError as DjangoValidationError
# serializers.py
from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db import connection
from django_tenants.utils import schema_context
from gymowners.models import GymTrainerOtherInfo

class GymActivityTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GymActivityType
        fields = ['type_name', 'type_description']  # Include type_description
        
    def validate_type_name(self, value):
        """Ensure that the activity type name is not empty and meets requirements."""
        if not value or value.strip() == '':
            raise serializers.ValidationError("Activity type name cannot be empty.")
        return value

    def validate(self, data):
        """Additional validation for the data."""
        if not data.get('type_description'):
            data['type_description'] = None  # Ensure empty description is saved as None
        return data

class GymActivityTypeResponseSerializer(serializers.ModelSerializer):
    """Serializer for GymActivityType model"""
    class Meta:
        model = GymActivityType
        fields = ['id', 'type_name', 'type_description', 'is_active', 'created_on', 'updated_on']
        read_only_fields = ['id', 'created_on', 'updated_on']


class GymActivityTypeDeleteSerializer(serializers.Serializer):
    """Serializer used for deleting multiple activity types by ID"""
    activity_type_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )

    def validate_activity_type_ids(self, value):
        existing_ids = set(GymActivityType.objects.filter(id__in=value).values_list('id', flat=True))
        missing_ids = [at_id for at_id in value if at_id not in existing_ids]
        if missing_ids:
            raise serializers.ValidationError(f"Activity type ids not found: {missing_ids}")
        return value

class GymActivityAssignedTrainerSerializer(serializers.ModelSerializer):
    """Serializer for GymActivityAssignedTrainer model"""
    class Meta:
        model = GymActivityAssignedTrainer
        fields = ['id', 'trainer', 'is_active', 'created_on', 'updated_on']
        read_only_fields = ['id', 'created_on', 'updated_on']


class GymActivityCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating gym activities"""
    activity_type = serializers.PrimaryKeyRelatedField(
        queryset=GymActivityType.objects.filter(is_active=True),
        help_text="ID of the activity type"
    )
    trainer_id = serializers.IntegerField(
        help_text="ID of the trainer to assign to this activity",
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = GymActivity
        fields = [
            'activity_name', 
            'activity_type', 
            'activity_description', 
            'repr', 
            'timing', 
            'days', 
            'intensity_level', 
            'max_participants', 
            'notes',
            'trainer_id'
        ]
    
    def validate_timing(self, value):
        """Validate timing is positive"""
        if value <= 0:
            raise serializers.ValidationError("Timing must be a positive number.")
        return value
    
    def validate_max_participants(self, value):
        """Validate max_participants is positive"""
        if value <= 0:
            raise serializers.ValidationError("Maximum participants must be a positive integer.")
        return value
    
    def validate_days(self, value):
        """Validate days array contains valid day choices"""
        if value:
            valid_days = [choice[0] for choice in settings.ACTIVITY_DAYS]
            for day in value:
                if day not in valid_days:
                    raise serializers.ValidationError(f"'{day}' is not a valid day choice.")
        return value
    
    def validate_intensity_level(self, value):
        """Validate intensity level is valid"""
        valid_levels = [choice[0] for choice in settings.ACTIVITY_INTENSITY_LEVELS]
        if value not in valid_levels:
            raise serializers.ValidationError(f"'{value}' is not a valid intensity level.")
        return value
    
    def validate_trainer_id(self, value):
        tenant_schema = connection.tenant.schema_name
        with schema_context(settings.PUBLIC_SCHEMA_NAME):
            user_model = get_user_model()
            if not user_model.objects.filter(id=value, is_active=True, role = settings.ROLE_GYM_TRAINER).exists():
                raise serializers.ValidationError("Invalid trainer ID.")
            gym_trainer_info = GymTrainerOtherInfo.objects.filter(user=value).first()
            if not gym_trainer_info:
                raise serializers.ValidationError("Trainer information not found.")
            if tenant_schema != gym_trainer_info.current_gym.schema_name:
                raise serializers.ValidationError("Trainer does not belong to this gym.")
        return value
    
    def validate_activity_type(self, value):
        """Validate activity type exists and is active"""
        if not value.is_active:
            raise serializers.ValidationError("Selected activity type is not active.")
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        # Check for duplicate activity names within the same type
        activity_name = attrs.get('activity_name')
        activity_type = attrs.get('activity_type')
        
        if GymActivity.objects.filter(
            activity_name__iexact=activity_name,
            activity_type=activity_type,
            is_active=True
        ).exists():
            raise serializers.ValidationError({
                'activity_name': 'An active activity with this name already exists for this activity type.'
            })
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """Create gym activity with trainer assignment"""
        trainer_id = validated_data.pop('trainer_id', None)
        
        try:
            # Create the activity first
            activity = GymActivity(**validated_data)
            activity.full_clean()  # Run model validation
            activity.save()
            
            # If trainer_id is provided, create the trainer assignment
            if trainer_id:
                trainer_assignment = GymActivityAssignedTrainer(
                    activity=activity,
                    trainer=trainer_id
                )
                trainer_assignment.full_clean()  # Run model validation including custom clean method
                trainer_assignment.save()
            
            return activity
            
        except DjangoValidationError as e:
            # If activity was created but trainer assignment failed, delete the activity
            if 'activity' in locals():
                activity.delete()
            raise serializers.ValidationError(e.message_dict if hasattr(e, 'message_dict') else str(e))


class GymActivityListSerializer(serializers.ModelSerializer):
    """Serializer for listing gym activities"""
    activity_type = GymActivityTypeSerializer(read_only=True)
    activity_type_name = serializers.CharField(source='activity_type.type_name', read_only=True)
    intensity_level_display = serializers.CharField(source='get_intensity_level_display', read_only=True)
    days_display = serializers.SerializerMethodField()
    assigned_trainers = serializers.SerializerMethodField()
    
    class Meta:
        model = GymActivity
        fields = [
            'id',
            'activity_name',
            'activity_type',
            'activity_type_name',
            'activity_description',
            'repr',
            'timing',
            'days',
            'days_display',
            'intensity_level',
            'intensity_level_display',
            'max_participants',
            'notes',
            'assigned_trainers',
            'is_active',
            'created_on',
            'updated_on'
        ]
    
    def get_days_display(self, obj):
        """Convert days array to display format"""
        if not obj.days:
            return []
        
        day_mapping = dict(settings.ACTIVITY_DAYS)
        return [day_mapping.get(day, day) for day in obj.days]
    
    def get_assigned_trainers(self, obj):
        """Get assigned trainers for the activity"""
        trainers = obj.assigned_trainers.filter(is_active=True)
        return [
            {
                'id': trainer.id,
                'trainer_id': trainer.trainer,
                'created_on': trainer.created_on,
                'is_active': trainer.is_active
            }
            for trainer in trainers
        ]
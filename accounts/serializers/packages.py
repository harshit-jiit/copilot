
from datetime import date, datetime, timedelta
import re
from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
from accounts.models.account_models import GymActivity
from utils.utils import to_aware_datetime
from accounts.models import GymPackageActivity, GymPackage


class GymActivitySerializer(serializers.ModelSerializer):
    """Serializer for GymActivity to be used in package views"""
    class Meta:
        model = GymActivity
        fields = ['id', 'activity_name']  # Adjust fields based on your GymActivity model

class GymPackageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating gym packages"""
    activity_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=True,
        help_text="List of activity IDs to associate with this package"
    )
    
    class Meta:
        model = GymPackage
        fields = [
            'package_name', 
            'package_price', 
            'package_duration', 
            'package_description',
            'is_active',
            'activity_ids'
        ]
    
    def validate_activity_ids(self, value):
        """Validate that all provided activity IDs exist and are active"""
        if value:
            activities = GymActivity.objects.filter(id__in=value, is_active=True)
            if len(activities) != len(value):
                raise serializers.ValidationError(
                    "One or more activities don't exist or are inactive"
                )
        return value
    
    def create(self, validated_data):
        activity_ids = validated_data.pop('activity_ids', [])
        
        # Create the package
        package = GymPackage.objects.create(**validated_data)
        
        # Create package-activity relationships
        if activity_ids:
            for activity_id in activity_ids:
                GymPackageActivity.objects.create(
                    gym_package=package,
                    activity_id=activity_id
                )
        
        return package

class GymPackageViewSerializer(serializers.ModelSerializer):
    """Serializer for viewing gym packages"""
    activities = serializers.SerializerMethodField()
    
    class Meta:
        model = GymPackage
        fields = [
            'id',
            'package_name',
            'package_price',
            'package_duration',
            'package_description',
            'is_active',
            'created_on',
            'updated_on',
            'activities'
        ]
    
    def get_activities(self, obj):
        """Get all active activities associated with this package"""
        package_activities = GymPackageActivity.objects.filter(
            gym_package=obj,
            is_active=True,
            activity__is_active=True
        ).select_related('activity')
        
        activities = [pa.activity for pa in package_activities]
        return GymActivitySerializer(activities, many=True).data
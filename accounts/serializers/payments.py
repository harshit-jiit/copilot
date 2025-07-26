
## serializers.py
from datetime import date
from rest_framework import serializers
from accounts.models import Payment
from django_tenants.utils import schema_context
from django.conf import settings
from django.contrib.auth import get_user_model
from accounts.models import GymMember

class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        # Exclude fields set automatically or by view
        exclude = ['payment_id', 'created_on', 'modified_on']

    def create(self, validated_data):
        # user is passed in context by the view
        return Payment.objects.create(**validated_data)

    # validate user
    def validate_user(self, value):
        if value is not None:
            with schema_context(settings.PUBLIC_SCHEMA_NAME):
                user_model = get_user_model()
                if not user_model.objects.filter(id=value, is_active=True, role=settings.ROLE_GYM_USER).exists():
                    raise serializers.ValidationError("Invalid member ID.")
            if not GymMember.objects.filter(user_id=value, is_active=True).exists():
                raise serializers.ValidationError("User is not a gym member.")  
        return value
        

class PaymentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        # Allow updating of mutable fields only
        fields = ['amount', 'tax_amount', 'payment_date', 'payment_method', 'status', 'remarks', 'transaction_reference_id']

class PaymentDeleteSerializer(serializers.Serializer):
    # Only needs payment_id to delete
    payment_id = serializers.UUIDField()

class PaymentFilterInputSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    def validate_user_ids(self, value):
        if value:
            with schema_context(settings.PUBLIC_SCHEMA_NAME):
                user_model = get_user_model()
                if not user_model.objects.filter(id__in=value, is_active=True, role=settings.ROLE_GYM_USER).exists():
                    raise serializers.ValidationError("One or more user IDs are invalid or inactive.")
        return value    
    
    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        if not start_date or not end_date:
            raise serializers.ValidationError("Both start_date and end_date are required.")
        if not isinstance(start_date, date) or not isinstance(end_date, date):
            raise serializers.ValidationError("start_date and end_date must be valid date objects.")
        # Ensure start_date is not after end_date
        if start_date > end_date:
            raise serializers.ValidationError("Start date cannot be after end date.")
        # Validate user_ids if provided
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("Start date cannot be after end date.")
    
        return data
    

class PaymentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['payment_id', 'user', 'invoice', 'amount', 'tax_amount', 'payment_date',
                  'payment_method', 'status', 'remarks', 'transaction_reference_id']
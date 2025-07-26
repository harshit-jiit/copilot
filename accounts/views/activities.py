from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView
from django.db import transaction

from accounts.permissions import IsAuthenticatedViaLoginSession, IsCheckUserActive, IsGymOwnerOrStaff
from accounts.models import GymActivity, GymActivityType
from accounts.serializers import (
    GymActivityTypeSerializer,
    GymActivityCreateSerializer,
    GymActivityListSerializer,
    GymActivityTypeResponseSerializer,
)


@extend_schema(
    request=GymActivityTypeSerializer(many=True),
    responses={
        201: GymActivityTypeSerializer(many=True)
    },
    description="Create or update multiple gym activity types. User must be authenticated and have appropriate role."
)
class GymActivityTypeCreateAPIView(APIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]

    @transaction.atomic
    def post(self, request):
        # Expecting an array of objects with type_name and type_description
        serializer = GymActivityTypeSerializer(data=request.data, many=True)
        if serializer.is_valid():
            results = []
            for item in serializer.validated_data:
                type_name = item.get('type_name')
                type_description = item.get('type_description')
                
                # Check if activity type exists (case-insensitive)
                existing_activity = GymActivityType.objects.filter(
                    type_name__iexact=type_name, 
                    is_active=True
                ).first()
                
                if existing_activity:
                    # Update description if activity exists
                    existing_activity.type_description = type_description
                    existing_activity.save()
                    if not existing_activity.type_name in [res['type_name'] for res in results]:
                        results.append({
                            'type_id': existing_activity.id,
                            'type_name': existing_activity.type_name,
                            'type_description': existing_activity.type_description,
                            'status': 'updated'
                    })
                else:
                    # Create new activity type
                    new_activity = GymActivityType.objects.create(
                        type_name=type_name,
                        type_description=type_description
                    )
                    if not new_activity.type_name in [res['type_name'] for res in results]:
                        results.append({
                            'type_id': new_activity.id,
                            'type_name': new_activity.type_name,
                            'type_description': new_activity.type_description,
                            'status': 'created'
                        })
                    
            return Response({
                'message': 'Activity types processed successfully.',
                'results': results
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    



@extend_schema(
    request=None,
    responses={
        200: GymActivityTypeResponseSerializer(many=True)
    },
    description="List all gym activity types. User must be authenticated and have appropriate role."
)
class GymActivityTypeListAPIView(ListAPIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]
    queryset = GymActivityType.objects.all()
    serializer_class = GymActivityTypeResponseSerializer




@extend_schema(
    request=GymActivityCreateSerializer,
    responses={
        201: GymActivityListSerializer
    },
    description="Create a new gym activity. User must be authenticated and have appropriate role."
)
class GymActivityCreateAPIView(generics.CreateAPIView):
    """API to create a new gym activity"""
    queryset = GymActivity.objects.all()
    serializer_class = GymActivityCreateSerializer
    permission_classes =  [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            activity = serializer.save()
            # Return the created activity with detailed information
            response_serializer = GymActivityListSerializer(activity)
            return Response(
                {
                    'message': 'Activity created successfully',
                    'data': response_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(
            {
                'message': 'Validation failed',
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(
    request=None,
    responses={
        200: GymActivityListSerializer(many=True)
    },
    description="List all gym activities. User must be authenticated."
)
class GymActivityListAPIView(generics.ListAPIView):
    """API to list gym activities"""
    queryset = GymActivity.objects.select_related('activity_type').prefetch_related('assigned_trainers').all()
    serializer_class = GymActivityListSerializer
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]

    @transaction.atomic
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'message': 'Activities retrieved successfully',
            'count': queryset.count(),
            'data': serializer.data
        })

from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from django.db import transaction
from accounts.permissions import IsAuthenticatedViaLoginSession, IsCheckUserActive, IsGymOwnerOrStaff
from accounts.models import GymPackage
from accounts.serializers import GymPackageCreateSerializer, GymPackageViewSerializer


@extend_schema(
    request=GymPackageCreateSerializer,
    responses={
        201: GymPackageViewSerializer,
        400: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'}
            }
        }
    },
    description="Create a new gym package with associated activities. User must be authenticated and have appropriate role."
)
class GymPackageCreateAPIView(generics.CreateAPIView):
    """API endpoint for creating gym packages"""
    queryset = GymPackage.objects.all()
    serializer_class = GymPackageCreateSerializer
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                package = serializer.save()
                
            # Return the created package with full details
            response_serializer = GymPackageViewSerializer(package)
            return Response(
                {
                    'success': True,
                    'message': 'Package created successfully',
                    'data': response_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'Error creating package: {str(e)}'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

@extend_schema(
    responses={
        200: GymPackageViewSerializer(many=True),
        404: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'}
            }
        }
    },
    parameters=[
        {
            'name': 'is_active',
            'in': 'query',
            'description': 'Filter by active status (true/false)',
            'required': False,
            'type': 'string'
        },
        {
            'name': 'package_name',
            'in': 'query',
            'description': 'Filter by package name (case-insensitive search)',
            'required': False,
            'type': 'string'
        }
    ],
    description="Retrieve list of gym packages with optional filtering. User must be authenticated."
)
class GymPackageListAPIView(generics.ListAPIView):
    """API endpoint for listing gym packages"""
    serializer_class = GymPackageViewSerializer
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]

    @transaction.atomic
    def get_queryset(self):
        """Get all active packages by default, allow filtering"""
        queryset = GymPackage.objects.all()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', 'true')
        if is_active.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active.lower() == 'false':
            queryset = queryset.filter(is_active=False)
        
        # Filter by package name (case-insensitive search)
        package_name = self.request.query_params.get('package_name')
        if package_name:
            queryset = queryset.filter(package_name__icontains=package_name)
        
        # Order by creation date (newest first)
        return queryset.order_by('-created_on')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response(
            {
                'success': True,
                'count': len(serializer.data),
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )

@extend_schema(
    responses={
        200: GymPackageViewSerializer,
        404: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'}
            }
        }
    },
    description="Retrieve detailed information about a specific gym package. User must be authenticated."
)
class GymPackageDetailAPIView(generics.RetrieveAPIView):
    """API endpoint for retrieving a single gym package"""
    queryset = GymPackage.objects.all()
    serializer_class = GymPackageViewSerializer
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]

    @transaction.atomic
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            
            return Response(
                {
                    'success': True,
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except GymPackage.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'Package not found'
                },
                status=status.HTTP_404_NOT_FOUND
            )
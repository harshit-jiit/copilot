from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django_tenants.utils import get_tenant
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model

from accounts.permissions import IsGymUser
from .serializers import GymOwnerRegistrationSerializer, PasswordUpdateSerializer
from utils.utils import generate_unique_subdomain, schema_mode
from gymowners.models import Client, Domain
from django.db import connection, transaction
from django.conf import settings

import uuid
import os

@extend_schema(
    request=GymOwnerRegistrationSerializer,
    responses={
        201: {
            "type": "object",
            "properties": {
                "message": {"type": "string", "example": "GymOwner registered successfully."},
                "tenant_id": {"type": "string", "example": "12345678"},
                "subdomain": {"type": "string", "example": "gym1.localhost"}
            }
        },
    },
    description="Register a new gym owner (tenant + user). Generates unique subdomain and tenant ID."
)
class GymOwnerRegistrationView(APIView):
    
    @schema_mode('public')
    @transaction.atomic
    def post(self, request):
        serializer = GymOwnerRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            gym_email = serializer.validated_data['gym_email']
            name = serializer.validated_data['gym_name']
            location = serializer.validated_data.get('gym_location', '')
            phone_number = serializer.validated_data.get('gym_phone_number', '')
            email = serializer.validated_data['gym_owner_email']
            password = serializer.validated_data['gym_owner_password']
            owner_name = serializer.validated_data['gym_owner_name']
            owner_phone_number = serializer.validated_data.get('gym_owner_phone_number', '')
            latitude = serializer.validated_data.get('latitude', None)
            longitude = serializer.validated_data.get('longitude', None)
     
            # Extract subdomain from host (assumes format like gym1.localhost)
            host = request.get_host()
            subdomain  = generate_unique_subdomain(name)

            # Create tenant schema
            tenant_id = str(uuid.uuid4())[:8]
            schema_name = tenant_id

            # setp 3 save the same user in main schema          
            User = get_user_model()
            user = User.objects.create(email=email,
                                       username=email,
                                       role='gym_owner',
                                       phone_number=owner_phone_number,
                                       first_name=owner_name,
                                       last_name=name,
                                       is_active=True,
                                       )
            user.set_password(password)
            user.save()

            client = Client.objects.create(
                schema_name=schema_name,
                gym_name=name,
                gym_location=location,
                gym_phone_number=phone_number,
                gym_email=gym_email,
                user=user,
                latitude=latitude,
                longitude=longitude,
            )

            # Step 2: Use nip.io for local/dev
            if settings.ENVIRONMENT == 'local':
                domain_name = f"{subdomain}.{settings.BASE_DOMAIN}.nip.io"
            else:
                domain_name = f"{subdomain}.{settings.BASE_DOMAIN}"

            Domain.objects.create(
                domain=domain_name,
                subdomain=subdomain,
                tenant=client,
                is_primary=True
            )

            return Response({
                "message": "Gym Details and Owner detaiils registered successfully.",
                "tenant_id": tenant_id,
                "subdomain": domain_name,

            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    responses={
        200: {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "ok"},
                "db": {"type": "string", "example": "connected"}
            }
        }
    },
    description="Simple health check to confirm API and database are reachable."
)
class HealthCheckView(APIView):
    authentication_classes = []  # public
    permission_classes = []      # allow all

    def get(self, request):
        if get_tenant(request).schema_name != 'public':
            return Response({"error": "This endpoint is only for public schema."}, status=403)
        # Optional: Check DB connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
        except Exception as e:
            return Response({"status": "error", "db": "unreachable", "error": str(e)}, status=500)

        return Response({"status": "ok", "db": "connected"}, status=status.HTTP_200_OK)


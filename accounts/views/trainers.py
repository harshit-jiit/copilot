import uuid
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from rest_framework.views import APIView
from datetime import datetime
from django.db import transaction
from accounts.serializers import AddGymTrainer, ActiveGymTrainerSerializer, AddGymTrainerResponse
from accounts.permissions import IsAuthenticatedViaLoginSession, IsCheckUserActive, IsGymOwnerOrStaff
from rest_framework.response import Response
from rest_framework import status
from django_tenants.utils import schema_context
from django.conf import settings
from django.db.models import F
from django.contrib.auth import get_user_model
from django_tenants.utils import get_tenant
from gymowners.models import GymTrainerOtherInfo, Client , TrainerGymHistory
from utils.utils import generate_random_password, schema_mode, send_password_email_html


@extend_schema(
    request=AddGymTrainer,
    description="Add a new gym trainer to the system.",
    responses={
        200: AddGymTrainerResponse
    }       
)
class AddGymTrainerView(APIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]
   
    @transaction.atomic
    def post(self, request):
        # Check if user is gym_owner or staff (superadmin/admin)
        user = request.user
        serializer = AddGymTrainer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        tenant = get_tenant(request)  # current gym

        first_name = serializer.validated_data['first_name']
        last_name = serializer.validated_data['last_name']
        middle_name = serializer.validated_data.get('middle_name', None)
        email = serializer.validated_data['email']
        phone_number = serializer.validated_data['phone_number']
        emergency_contact_number = serializer.validated_data.get('emergency_contact_number', None)
        date_of_birth = serializer.validated_data['date_of_birth']
        gender = serializer.validated_data['gender']
        address = serializer.validated_data['address']
        blood_group = serializer.validated_data.get('blood_group', None)
        medical_condition = serializer.validated_data.get('medical_condition', None)
        past_experience = serializer.validated_data.get('past_experience', None)
        certifications = serializer.validated_data.get('certifications', None)
        specializations = serializer.validated_data.get('specializations', None)


        # Generate random password
        password = generate_random_password()

        # Create new user with gym_user role
        with schema_context(settings.PUBLIC_SCHEMA_NAME):
            user_model = get_user_model()
            new_user = user_model.objects.create(
                username=email,
                email=email,
                phone_number=phone_number,
                role=settings.ROLE_GYM_TRAINER,  # Assuming ROLE_GYM_USER is defined in settings
                first_name= first_name,
                last_name= last_name,
                middle_name= middle_name,
                is_active=True
                                        )
            new_user.set_password(password)
            new_user.save()
            
            gym_id = Client.objects.get(schema_name = request.tenant_schema)
            GymTrainerOtherInfo.objects.create(
                user=new_user,
                current_gym=gym_id,
                emergency_contact_number=emergency_contact_number,
                date_of_birth=date_of_birth,
                gender=gender,
                address=address,
                blood_group=blood_group,
                medical_conditions=medical_condition,
                past_experience=past_experience,
                certifications=certifications,
                specialization=specializations,
                is_active=True
            )
            # add the entry to the trainer gym history table
            TrainerGymHistory.objects.create(
                trainer=new_user,
                gym=gym_id,
                start_date = datetime.now().date(),
                is_active=True
            )
        

        # Send password email
        # mail_response = send_password_email_html(
        #     email=email,
        #     password=password,
        #     package_name=package.package_name if package_id else "No Package",
        #     package_duration=package.package_duration if package_id else "N/A",
        #     gym_name=tenant.gym_name,
        #     gym_location= tenant.gym_location
        # )
        # if mail_response.status_code != 200:
        #     return Response({"detail": "Member created but failed to send password email."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {"detail": "Member created successfully.",
             "gym_member_id": new_user.id,
             "gym_id": gym_id.id},
             status=status.HTTP_201_CREATED
        )
    
@extend_schema(
    request=None,
    responses={
        200: ActiveGymTrainerSerializer(many=True)
    },
    description="List all active gym members for the current tenant gym. User must be authenticated and have appropriate role."
)
class ActiveGymTrainersView(APIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]

    def get(self, request):
        tenant = get_tenant(request)
        gym_id = Client.objects.get(schema_name = request.tenant_schema)
        with schema_context("public"):
            trainers = GymTrainerOtherInfo.objects.filter(is_active=True, current_gym=gym_id).order_by('-created_on').annotate(
                    email=F('user__email'),
                    first_name=F('user__first_name'),
                    last_name=F('user__last_name'),
                    middle_name=F('user__middle_name'),
                    phone_number=F('user__phone_number'),
                    role=F('user__role'),
                    trainer_id=F('user__id'),
            ).values(
                'emergency_contact_number', 'date_of_birth', 'gender', 'address',
                'blood_group', 'medical_conditions', 'past_experience', 'certifications',
                'specialization', 'user__id', 'email', 'first_name',
                'last_name', 'middle_name', 'phone_number', 'role', 'trainer_id'
            )
            if not trainers:
                return Response({"detail": "No active trainers found."}, status=status.HTTP_404_NOT_FOUND)
            serializer = ActiveGymTrainerSerializer(trainers, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)           
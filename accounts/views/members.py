import uuid
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from rest_framework.views import APIView
from django.db import transaction
from accounts.models import GymPackage
from accounts.permissions import IsAuthenticatedViaLoginSession, IsCheckUserActive, IsGymOwnerOrStaff
from rest_framework.response import Response
from rest_framework import status
from django_tenants.utils import schema_context
from django.conf import settings
from django.contrib.auth import get_user_model
from django_tenants.utils import get_tenant
from accounts.models import GymMember, GymPackage
from accounts.models.account_models import GymMembersCustomActivity
from gymowners.models import GymUserOtherInfo, Client, UserGymHistory
from utils.utils import generate_random_password, schema_mode, send_password_email_html
from accounts.serializers import AddGymMemberSerializer, ActiveGymMemberSerializer
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from accounts import serializers
from datetime import timedelta
# import boto3


  
@extend_schema(
    request=AddGymMemberSerializer,
    responses={
        201: {
            "type": "object",
            "properties": {
                "detail": {"type": "string"}
            }
        }
    },
    description="Add a new gym member for the current tenant gym. User must be authenticated and have appropriate role."
)
class AddGymMemberView(APIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]

    @transaction.atomic
    def post(self, request):
        # Check if user is gym_owner or staff (superadmin/admin)
        user = request.user
  
        serializer = AddGymMemberSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        tenant = get_tenant(request)  # current gym
        gym_id = Client.objects.get(schema_name = request.tenant_schema)
        first_name = serializer.validated_data.get('first_name')
        last_name = serializer.validated_data.get('last_name')
        middle_name = serializer.validated_data.get('middle_name')
        email = serializer.validated_data.get('email')
        phone_number = serializer.validated_data.get('phone_number')
        emergency_contact_number = serializer.validated_data.get('emergency_contact_number')
        date_of_birth = serializer.validated_data.get('date_of_birth')
        gender = serializer.validated_data.get('gender')
        address = serializer.validated_data.get('address')
        blood_group = serializer.validated_data.get('blood_group')
        height = serializer.validated_data.get('height')
        weight = serializer.validated_data.get('weight')
        batch = serializer.validated_data.get('batch')
        medical_conditions = serializer.validated_data.get('medical_conditions')
        fitness_goals = serializer.validated_data.get('fitness_goals')
        notes = serializer.validated_data.get('notes')
        attachments = serializer.validated_data.get('attachments')
        trainer_id = serializer.validated_data.get('trainer_id')
        membership_start_date = serializer.validated_data.get('membership_start_date')
        membership_end_date = serializer.validated_data.get('membership_end_date')
        package_id = serializer.validated_data.get('package_id')
        referred_by = serializer.validated_data.get('referred_by')
        activity_ids = serializer.validated_data.get('activity_ids', [])

        file_urls = []

        if attachments:
            for file in attachments:
                path = default_storage.save(f'attachments/{file.name}', ContentFile(file.read()))
                # full_url = self.context['request'].build_absolute_uri(default_storage.url(path))
                full_url = request.build_absolute_uri(default_storage.url(path))

                file_urls.append(full_url)

        # elif upload_to == 's3':
        #     s3 = boto3.client(
        #         's3',
        #         aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        #         aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        #     )
        #     for file in files:
        #         file_key = f'attachments/{file.name}'
        #         s3.upload_fileobj(file, settings.AWS_STORAGE_BUCKET_NAME, file_key)
        #         file_url = f'https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{file_key}'
        #         file_urls.append(file_url)


        # Generate random password
        password = generate_random_password()

        # Create new user with gym_user role
        with schema_context(settings.PUBLIC_SCHEMA_NAME):
            user_model = get_user_model()
            new_user = user_model.objects.create(
                username=email,
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                email=email,
                phone_number=phone_number,
                role=settings.ROLE_GYM_USER,  # Assuming ROLE_GYM_USER is defined in settings
                is_active=True
                                        )
            new_user.set_password(password)
            new_user.save()

            GymUserOtherInfo.objects.create(
                user=new_user,
                current_gym= gym_id,
                emergency_contact_number=emergency_contact_number,
                address=address,
                batch=batch,
                height=height,
                weight=weight,
                blood_group=blood_group,
                medical_conditions=medical_conditions,
                fitness_goals=fitness_goals,
                notes=notes,
                attachments=file_urls,
                date_of_birth=date_of_birth,
                gender=gender
            )

            UserGymHistory.objects.create(
                user=new_user,
                gym=gym_id,
                start_date=membership_start_date,
                is_active=True
            )
            
        if membership_start_date and membership_end_date and activity_ids:
            GymMember.objects.create(
                user_id=new_user.id,
                trainer_id=trainer_id,
                membership_start_date=membership_start_date,
                membership_end_date=membership_end_date,
                membership_status='active',
                is_active=True,
                referred_by=referred_by
            )
            GymMembersCustomActivity.objects.bulk_create([
                GymMembersCustomActivity(
                    user=new_user.id,
                    activity_id=activity_id
                ) for activity_id in activity_ids   
            ])
        elif membership_start_date and membership_end_date and package_id:
            package = GymPackage.objects.get(id=package_id)
            GymMember.objects.create(
                user_id=new_user.id,
                trainer_id=trainer_id,
                membership_start_date=membership_start_date,
                membership_end_date=membership_start_date + timedelta(days=package.package_duration),
                package=package,
                membership_status='active',
                is_active=True,
                referred_by=referred_by
            )
            
        print(f"New member created: {new_user.username} with password: {password}")
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

        return Response({"detail": "Gym member created and password sent via email."}, status=status.HTTP_201_CREATED)
    

@extend_schema(
    request=None,
    responses={
        200: ActiveGymMemberSerializer(many=True)
    },
    description="List all active gym members for the current tenant gym. User must be authenticated and have appropriate role."
)
class ActiveGymMembersView(APIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]

    # @transaction.atomic
    def get(self, request):
        tenant = get_tenant(request)
        a_members =[]
        active_members = GymMember.objects.filter(membership_status='active')
        for member in active_members:
            with schema_context(settings.PUBLIC_SCHEMA_NAME):
                user_info = GymUserOtherInfo.objects.filter(user=member.user_id).first()
            if user_info:
                a_members.append({
                    'user_id': user_info.user_id,
                    'email': user_info.user.email,
                    'first_name': user_info.user.first_name,
                    'last_name': user_info.user.last_name,
                    'middle_name': user_info.user.middle_name,  
                    'phone_number': user_info.user.phone_number,
                    'emergency_contact_number': user_info.emergency_contact_number,
                    'date_of_birth': user_info.date_of_birth,
                    'gender': user_info.gender, 
                    'address': user_info.address,
                    'blood_group': user_info.blood_group,
                    'height': user_info.height,
                    'weight': user_info.weight,
                    'batch': user_info.batch,
                    'medical_conditions': user_info.medical_conditions,
                    'fitness_goals': user_info.fitness_goals,
                    'notes': user_info.notes,
                    # 'attachments': user_info.attachments,
                    'membership_start_date': member.membership_start_date,
                    'membership_end_date': member.membership_end_date,
                    'membership_status': member.membership_status,
                    'package_id': member.package_id if member.package_id else None,
                    'package_name': member.package.package_name if member.package else None,
                    'referred_by': member.referred_by,
                    'trainer_id': member.trainer_id,
                    'custom_activity_ids': GymMembersCustomActivity.objects.filter(
                        user=member.user_id, is_active=True
                    ).values_list('activity_id', flat=True),
                })

        serializer = ActiveGymMemberSerializer(a_members, many=True)
        return Response(serializer.data)
    


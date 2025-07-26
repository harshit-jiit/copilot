from datetime import timedelta
from django.forms import ValidationError
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.contrib.auth import authenticate, get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django_tenants.utils import schema_context
from accounts.permissions import IsAuthenticatedViaGymUserLoginSession, IsCheckUserActive, IsGymUser
from utils.utils import schema_mode, get_token_via_header
from gymowners.models import Domain, GymUserOtherInfo,Client
from accounts.models import LoginSession, Attendance, GymMember
from gym_mobileapp.serializers import (
    LoginSerializer,
    RefreshTokenSerializer,
    LoginResponseSerializer,
    TokenRefreshResponseSerializer,
    PasswordUpdateSerializer,
    AttendanceSerializer,
    PunchOutSerializer,
    UserDetailSerializer,
    TrainerSerializer,
    ClientSerializer
)
from django.shortcuts import get_object_or_404

@extend_schema(
    request=LoginSerializer,
    description="Login a user with email and password to receive JWT and refresh tokens",
    responses={
        200: LoginResponseSerializer
    }       
)
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    @transaction.atomic
    @schema_mode('public')
    def post(self, request):

        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        # Step 2: Ensure user exists in public schema
        try:
            user_model = get_user_model()
            user = user_model.objects.get(email=email)
            # Step 4: Authenticate user
            user = authenticate(request, username=email, password=password)
            if user is None:
                return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
            if user.is_active is False:
                return Response({"detail": "User account is inactive."}, status=status.HTTP_403_FORBIDDEN)
            if user.role != settings.ROLE_GYM_USER:
                return Response({"detail": "Only gym users can access this resource."}, status=status.HTTP_403_FORBIDDEN)
            gym_user_info = GymUserOtherInfo.objects.get(user=user)
            user_subdomain = Domain.objects.get(
                tenant__user= gym_user_info.current_gym.user,
                is_primary=True
            )
        except user_model.DoesNotExist:
            return Response({"detail": "Invalid credentials or user does not exist in this tenant."}, status= status.HTTP_404_NOT_FOUND)
        except Domain.DoesNotExist:
            return Response({"detail": "User does not belong to this Gym."}, status=status.HTTP_403_FORBIDDEN)

        jwt_token = get_token_via_header(request)

        if jwt_token:
            jwt_authenticator = JWTAuthentication()
            try:
                validated_token = jwt_authenticator.get_validated_token(jwt_token)
                user = jwt_authenticator.get_user(validated_token)
                with schema_context(user_subdomain.tenant.schema_name):
                    active_session = LoginSession.objects.filter(user_id=user.id,
                                                                logout_time__isnull=True,
                                                                refresh_expires_at__gt=timezone.now(),
                                                                jwt_token=  jwt_token,
                                                                jwt_expires_at__gt=timezone.now())
                    if active_session:
                        return Response({
                            "detail": "User is already logged in with a valid token.",
                            "user": user.email
                        }, status=200)

            except (InvalidToken, TokenError):
                pass  # Continue with login if token is invalid/expired

        # Step 5: Generate tokens
        refresh = RefreshToken.for_user(user)
        # hashed_refresh = hashlib.sha256(str(refresh).encode()).hexdigest()

        access_token = str(refresh.access_token)  # Convert access token to string
        now = timezone.now()
        jwt_exp = now + timedelta(hours=settings.JWT_TOKEN_EXPIRY_HOURS)
        refresh_exp = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS)
        # Step 6: Save login session
            
        with schema_context(user_subdomain.tenant.schema_name):
            LoginSession.objects.create(
                user_id=user.id,
                domain_id =user_subdomain.id,
                jwt_created_at=now,
                jwt_expires_at=jwt_exp,
                refresh_created_at=now,
                refresh_expires_at=refresh_exp,
                jwt_token=access_token,
                refresh_token=str(refresh))
            
        user.last_login = timezone.now()
        user.save()
        res =  Response({
            'user': user.email,
            'tenant_id': user_subdomain.tenant.schema_name,
            'subdomain': user_subdomain.domain,
            'jwt_token': access_token, # temporary access token for frontend
            'refresh_token': str(refresh),  # temporary refresh token for frontend
        }, status=200)

        return res


@extend_schema(
    request=None,
    responses={200: {"type": "object", "properties": {"message": {"type": "string"}}}},
    description="Logs out the current session only using JWT access token."
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticatedViaGymUserLoginSession, IsGymUser, IsCheckUserActive]

    @transaction.atomic
    def post(self, request):
        jwt_token = get_token_via_header(request)  # Ensure the token is fetched from headers
        now = timezone.now()
        # with schema_context(request.tenant.schema_name):
        try:
            sess = LoginSession.objects.get(
                user_id=request.user.id,
                jwt_token=jwt_token,
                logout_time__isnull=True,
                refresh_expires_at__gt=now,
                jwt_expires_at__gt=now
            )
            sess.logout_time = now
            sess.save()
            res =  Response({"detail": "Logged out successfully"}, status=status.HTTP_200_OK)
        except LoginSession.DoesNotExist:
            return Response({"detail": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            return Response({"detail": "Logout failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        res.delete_cookie('jwt_token')
        res.delete_cookie('refresh_token')
        return res


@extend_schema(
    request=RefreshTokenSerializer,
    description="Refresh JWT token and update the login session with new expiration times",
    responses={
        200: TokenRefreshResponseSerializer 
    }       
)
class CustomTokenRefreshView(TokenRefreshView):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            try:
                refresh_token = request.data['refresh']
                user_id = RefreshToken(refresh_token)['user_id']
                user = get_user_model().objects.get(id=user_id)
                session = LoginSession.objects.get(
                    user_id=user.id,

                    refresh_token=refresh_token,
                    logout_time__isnull=True
                )
                access_token = response.data.get('access')
                session.jwt_token = access_token
                session.jwt_created_at = timezone.now()
                session.jwt_expires_at = timezone.now() + timedelta(hours=settings.JWT_TOKEN_EXPIRY_HOURS)
                session.save()
                
            except LoginSession.DoesNotExist:
                return Response({"detail": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                print(f"Failed to update session on refresh: {str(e)}")
                return Response({"detail": "Failed to update session."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "access": response.data.get('access'),
            "expires_datetime": (timezone.now() + timedelta(hours=settings.JWT_TOKEN_EXPIRY_HOURS)).isoformat(),
        }, status=response.status_code)


@extend_schema(
    request=PasswordUpdateSerializer,
    description="Update the password for the authenticated user",
    responses={
        200: {"type": "object", "properties": {"message": {"type": "string"}}},
        400: {"type": "object", "properties": {"error": {"type": "string"}}}
    }
)
class PasswordUpdateView(APIView):
    permission_classes = [IsAuthenticatedViaGymUserLoginSession, IsGymUser, IsCheckUserActive]
    serializer_class = PasswordUpdateSerializer

    @transaction.atomic
    @schema_mode('public')
    def post(self, request):
        serializer = PasswordUpdateSerializer(data=request.data,  context={'request': request})
        user = request.user

        if serializer.is_valid():
            old_password = serializer.validated_data['old_password']
            new_password = serializer.validated_data['new_password']

            if not user.check_password(old_password):
                return Response({'detail': 'Old password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
        
            user.set_password(new_password)
            user.save()
            return Response({'detail': 'Password updated successfully.'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    request=AttendanceSerializer,
    description="Punch in to start attendance tracking",
    responses={
        201: {"type": "object", "properties": {"message": {"type": "string"}}},
        400: {"type": "object", "properties": {"error": {"type": "string"}}}
    }
)
class PunchInAPIView(APIView):
    permission_classes = [IsAuthenticatedViaGymUserLoginSession, IsGymUser, IsCheckUserActive]

    @transaction.atomic
    def post(self, request):
        try:
            user = request.user
            # Prevent duplicate punch in without punch out
            if Attendance.objects.filter(user=user.id, punch_out_time__isnull=True).exists():
                return Response({"detail": "You already punched in and not punched out."}, status=status.HTTP_400_BAD_REQUEST)

            serializer = AttendanceSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                # Validate that if  user for today already punched in and not punched out till now, then he can't punch in 
                if Attendance.objects.filter(
                    user=user.id,
                    punch_in_time__date=timezone.now().date(),
                    punch_out_time__isnull=True
                ).exists():
                    return Response({"detail": "You have already punched in today."}, status=status.HTTP_400_BAD_REQUEST)
                Attendance.objects.create(
                    user=user.id,
                    latitude=serializer.validated_data.get('latitude'),
                    longitude=serializer.validated_data.get('longitude'),
                    punch_in_time=timezone.now()
                )
                return Response({"detail": "Punched in successfully"}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as ve:
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    request=PunchOutSerializer,
    description="Punch out to end attendance tracking",
    responses={
        200: {"type": "object", "properties": {"message": {"type": "string"}}},
        400: {"type": "object", "properties": {"error": {"type": "string"}}}
    }
)
class PunchOutAPIView(APIView):
    permission_classes = [IsAuthenticatedViaGymUserLoginSession, IsGymUser, IsCheckUserActive]

    @transaction.atomic
    def post(self, request):
        serializer = PunchOutSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # attendance_id = serializer.validated_data['attendance_id']
            # punch out for today's attendance
            user = request.user
            attendance = Attendance.objects.filter(
                user=user.id,
                punch_out_time__isnull=True
            ).order_by('-punch_in_time').first()
            if attendance is None:
                return Response({"detail": "No active punch in found."}, status=status.HTTP_400_BAD_REQUEST)

    
            attendance.punch_out_time = timezone.now()
            attendance.save()
            return Response({"detail": "Punched out successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    request=None,
    description="List all attendance records for the authenticated user",
    responses={
        200: AttendanceSerializer(many=True)
    }
)
class AttendanceListAPIView(APIView):
    permission_classes = [IsAuthenticatedViaGymUserLoginSession, IsGymUser, IsCheckUserActive]

    def get(self, request):
        user = request.user
        attendance_records = Attendance.objects.filter(user=user.id).order_by('-punch_in_time')
        serializer = AttendanceSerializer(attendance_records, many=True)
        return Response(serializer.data)
    
@extend_schema(
    request=None,
    description="Get the user profile including CustomUser and GymUserOtherInfo",
    responses={
        200: UserDetailSerializer
    }
)
class UserProfileAPIView(APIView):
    """
    GET /api/user/profile/
    Returns the CustomUser + GymUserOtherInfo for the user authenticated by the JWT.
    """
    permission_classes = [IsAuthenticatedViaGymUserLoginSession, IsGymUser, IsCheckUserActive]

    @transaction.atomic
    @schema_mode('public')
    def get(self, request):
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data)
    

@extend_schema(
    request=None,
    description="Get the trainer profile for the authenticated user",
    responses={
        200: TrainerSerializer
    }
)
class TrainerProfileAPIView(APIView):
    """
    GET /api/user/profile/
    Returns the CustomUser + GymUserOtherInfo for the user authenticated by the JWT.
    """
    permission_classes = [IsAuthenticatedViaGymUserLoginSession, IsGymUser, IsCheckUserActive]

    @transaction.atomic
    @schema_mode('public')
    def get(self, request):
        gym_user_details = GymUserOtherInfo.objects.get(user=request.user)
        current_gym = gym_user_details.current_gym
        # fetch the schema name of the gym
        schema_name = Client.objects.get(id=current_gym.id).schema_name
        with schema_context(schema_name):
            trainer = GymMember.objects.get(user_id=request.user.id).trainer_id
            if not trainer:
                return Response({"detail": "No trainer assigned to this user."}, status=404)
        trainer = get_user_model().objects.get(id=trainer)
        serializer = TrainerSerializer(trainer)
        return Response(serializer.data)

@extend_schema(
    request=None,
    description="Get the gym profile for the authenticated user",
    responses={
        200: ClientSerializer
    }
)
class GymProfileView(APIView):
    permission_classes = [IsAuthenticatedViaGymUserLoginSession, IsGymUser, IsCheckUserActive]

    @transaction.atomic
    @schema_mode('public')
    def get(self, request):
        # Get the Client profile associated with the authenticated user
        current_gym = GymUserOtherInfo.objects.get(user=request.user).current_gym
        client = get_object_or_404(Client, id=current_gym.id)
        serializer = ClientSerializer(client)
        return Response(serializer.data)
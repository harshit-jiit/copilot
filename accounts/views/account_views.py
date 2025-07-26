from datetime import timedelta
import hashlib
import uuid
from django_tenants.utils import schema_context
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import authenticate
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django_tenants.utils import get_tenant
from accounts.models.account_models import Attendance, Payment
from accounts.permissions import IsAuthenticatedViaLoginSession, IsCheckUserActive, IsGymOwnerOrStaff
from utils.utils import generate_random_password, schema_mode, send_password_email_html
from gymowners.models import CustomUser, Domain
from accounts.models import GymMember, LoginSession
from django.db import transaction
from rest_framework_simplejwt.authentication import JWTAuthentication

from rest_framework import status
from accounts.serializers import LoginSerializer,RefreshTokenSerializer, LoginResponseSerializer, TokenRefreshResponseSerializer, DashboardResponseSerializer, DashboardActiveMemberSerializer
from accounts import serializers
import os
from utils.utils import get_token_via_header, get_token_via_cookies, set_cookies, delete_cookies
from django.db.models import Sum

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
            return Response(serializer.errors, status=400)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        try:
            user_model = get_user_model()
            user = user_model.objects.get(email=email)
            # Step 4: Authenticate user
            user = authenticate(request, username=email, password=password)
            if user is None:
                return Response({"detail": "Invalid credentials."}, status=401)
            if user.is_active is False:
                return Response({"detail": "User account is inactive."}, status=403)
            if user.role != settings.ROLE_GYM_OWNER:
                return Response({"detail": "Only gym owners can access this resource."}, status=403)
            user_subdomain = Domain.objects.get(
                # tenant=tenant,
                tenant__user=user,
                is_primary=True
            )
        except user_model.DoesNotExist:
            return Response({"detail": "Invalid credentials or user does not exist."}, status=401)
        except User.DoesNotExist:
            return Response({"detail": "Invalid credentials or user does not exist in this tenant."}, status=401)
        except Domain.DoesNotExist:
            return Response({"detail": "User does not belong to this tenant."}, status=401)

        # jwt_token = get_token_via_cookies(request)       
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
                                                                jwt_token=jwt_token,
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
            'a_c': access_token, # temporary access token for frontend
            'r_t': str(refresh),  # temporary refresh token for frontend
        }, status=200)

        # cookie_host = user_subdomain.domain.replace(user_subdomain.subdomain, '')
        
        # set_cookies(
        #     res,
        #     jwt_token=access_token,
        #     refresh_token=str(refresh),
        #     domain=cookie_host.strip()
        # )
    
        return res


@extend_schema(
    request=None,
    responses={200: {"type": "object", "properties": {"message": {"type": "string"}}}},
    description="Logs out the current session only using JWT access token."
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]

    @transaction.atomic
    def post(self, request):
        # jwt_Token = get_token_via_cookies(request)
        jwt_Token = get_token_via_header(request)
        now = timezone.now()
        # with schema_context(request.tenant.schema_name):
        try:
            sess = LoginSession.objects.get(
                user_id=request.user.id,
                jwt_token=jwt_Token,
                logout_time__isnull=True,
                refresh_expires_at__gt=now,
                jwt_expires_at__gt=now
            )
            sess.logout_time = now
            sess.save()
            res =  Response({"message": "Logged out successfully"}, status=200)
        except LoginSession.DoesNotExist:
            return Response({"detail": "Session not found."}, status=404)
        except Exception as e:
            print(f"Logout failed: {str(e)}")
            return Response({"detail": "Logout failed."}, status=500)

        # delete_cookies(res)
        return res

@extend_schema(
    request=None,
    responses={200: {"type": "object", "properties": {"detail": {"type": "string"}, "user": {"type": "string"}, "tenant_id": {"type": "string"}, "subdomain": {"type": "string"}}}},
    description="Check if the user is authenticated using the JWT token stored in cookies."
)
class CheckAuthenticatedView(APIView):
    permission_classes = [permissions.AllowAny]

    @schema_mode('public')
    @transaction.atomic
    def get(self, request):
        # jwt_token  = get_token_via_cookies(request)
        jwt_token = get_token_via_header(request)
        # decode jwt token to get user id
        try:
            if not jwt_token:
                return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)
            jwt_authenticator = JWTAuthentication()
            validated_token = jwt_authenticator.get_validated_token(jwt_token)
            user_id = jwt_authenticator.get_user(validated_token)
            if not user_id:
                return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)

            user = get_user_model().objects.get(id=user_id.id, is_active=True, role=settings.ROLE_GYM_OWNER)
            user_subdomain = Domain.objects.get(tenant__user=user,is_primary=True)

            with schema_context(user_subdomain.tenant.schema_name):
                # Check if the session exists and is valid
                # with schema_context(request.tenant.schema_name):
                    session = LoginSession.objects.get(
                        jwt_token=jwt_token,
                        logout_time__isnull=True,
                        user_id=user.id,
                        refresh_expires_at__gt=timezone.now(),
                        jwt_expires_at__gt=timezone.now()
                    )
                    
            res =  Response({"detail": "User is authenticated.",
                'user': user.email,
                'tenant_id': user_subdomain.tenant.schema_name,
                'subdomain': user_subdomain.domain,
            }, status=status.HTTP_200_OK)
            
            # cookie_host = user_subdomain.domain.replace(user_subdomain.subdomain, '')

            # set_cookies(
            #     res,
            #     jwt_token=jwt_token,
            #     refresh_token=refresh_token,    
            #     domain=cookie_host.strip()
            # )
            return res
        except LoginSession.DoesNotExist:
            return Response({"detail": "Not authenticated."}, status=404)
        except Domain.DoesNotExist:
            return Response({"detail": "Not authenticated."}, status=404)


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
                # with schema_context(request.tenant.schema_name):
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
                return Response({"detail": "Session not found."}, status=404)
            except Exception as e:
                print(f"Failed to update session on refresh: {str(e)}")

        return Response({
            "access": response.data.get('access'),
            "expires_datetime": (timezone.now() + timedelta(hours=settings.JWT_TOKEN_EXPIRY_HOURS)).isoformat(),
        })




@extend_schema(
    summary="Get dashboard statistics for the current gym",
    description="Returns revenue, member count, and list of today's active members.",
    responses={200: DashboardResponseSerializer},
    tags=['Dashboard'],
    operation_id='dashboard_stats',
)
class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]

    @transaction.atomic
    def get(self, request):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        # Revenue
        revenue = Payment.objects.filter(
            payment_date__date__gte=month_start,
            payment_date__date__lte=today,
            status='paid'
        ).aggregate(total=Sum('amount'))['total'] or 0

        # Members
        member_ids = GymMember.objects.filter(
            membership_start_date__date__gte=month_start,
            membership_start_date__date__lte=today
        ).values_list('user_id', flat=True).distinct()
        member_count = member_ids.count()

        # Active Members
        attendances = Attendance.objects.filter(
            punch_in_time__date=today
        ).select_related(None)
        active_members = []
        user_ids_today = set()
        for att in attendances:
            if att.user not in user_ids_today:
                user_ids_today.add(att.user)
                try:
                    with schema_context(settings.PUBLIC_SCHEMA_NAME):
                        CustomUser = get_user_model()
                        user = CustomUser.objects.get(id=att.user, is_active=True, role=settings.ROLE_GYM_USER)
                    gym_member = GymMember.objects.filter(user_id=user.id).first()
                except CustomUser.DoesNotExist:
                    continue
                active_members.append({
                    'id': user.id,
                    'name': f"{user.first_name} {user.last_name}".strip(),
                    'check_in': att.punch_in_time.strftime('%I:%M %p') if att.punch_in_time else None,
                    'check_out': att.punch_out_time.strftime('%I:%M %p') if att.punch_out_time else None,
                    'payment_due_date': gym_member.membership_end_date.strftime('%d-%m-%Y') if gym_member and gym_member.membership_end_date else None
                })

        serializer = DashboardResponseSerializer({
            "Revenue": revenue,
            "Members": member_count,
            "active_members": active_members
        })
        return Response(serializer.data, status=200)
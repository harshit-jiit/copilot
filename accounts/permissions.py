# permissions.py
from rest_framework.permissions import BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from django_tenants.utils import get_tenant
from django_tenants.utils import schema_context
from django.conf import settings
from accounts.models import GymMember, LoginSession  # adjust to your app name
from gymowners.models import Client, GymUserOtherInfo  # adjust to your app name
from django.db import transaction
from utils.utils import get_token_via_header, get_token_via_cookies
from rest_framework import status
import jwt
from rest_framework.exceptions import NotFound


class IsAuthenticatedViaLoginSession(BasePermission):
    @transaction.atomic
    def has_permission(self, request, view):
        # jwt_token, refresh_token = get_token_via_cookies(request)  # Ensure the token is fetched from cookies
        jwt_token = get_token_via_header(request)
        if jwt_token:
            jwt_authenticator = JWTAuthentication()
            try:
                validated_token = jwt_authenticator.get_validated_token(jwt_token)
                user = jwt_authenticator.get_user(validated_token)
                if validated_token.get('token_type') != 'access':
                    raise AuthenticationFailed("Refresh token not allowed.")
                now = timezone.now()
                session = LoginSession.objects.get(
                    user_id=user.id,
                    jwt_token=jwt_token,
                    logout_time__isnull=True,
                    refresh_expires_at__gt=now,
                    jwt_expires_at__gt=now
                )
                with schema_context(settings.PUBLIC_SCHEMA_NAME):
                    if not Client.objects.filter(
                        user_id=user.id,
                        schema_name=request.tenant_schema
                    ).exists():
                        raise AuthenticationFailed("User does not belong to the tenant.")
                request.user = user  # attach user manually
                return True
            except LoginSession.DoesNotExist:
                raise AuthenticationFailed("Login session does not exist or has expired.")
            except Exception as e:
                raise AuthenticationFailed(f"Authentication failed: {str(e)}")
        else:
            raise AuthenticationFailed("Missing JWT token in cookies.")

# create a permission that the role should be to gym owner and gym staff
class IsGymOwnerOrStaff(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        
        # Check if the user is a gym owner or staff
        if user.role in [settings.ROLE_GYM_OWNER, settings.ROLE_GYM_STAFF]:
            return True
        
        # If the user is not a gym owner or staff, deny access
        return False
    
class IsGymUser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        
        # Check if the user is a gym user
        if user.role == settings.ROLE_GYM_USER:
            return True
        
        # If the user is not a gym user, deny access
        return False
    
class IsCheckUserActive(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        
        # Check if the user is active
        if user.is_active:
            return True
        
        # If the user is not active, deny access
        return False


class IsAuthenticatedViaGymUserLoginSession(BasePermission):
    @transaction.atomic
    def has_permission(self, request, view):
        # jwt_token = get_token_via_cookies(request)  # Ensure the token is fetched from cookies
        jwt_token = get_token_via_header(request)
        # set exception for expired token

        if jwt_token:
            jwt_authenticator = JWTAuthentication()
            try:
                validated_token = jwt_authenticator.get_validated_token(jwt_token)
                user = jwt_authenticator.get_user(validated_token)
                if validated_token.get('token_type') != 'access':
                    raise AuthenticationFailed("Refresh token not allowed.", code= status.HTTP_401_UNAUTHORIZED)
                now = timezone.now()
                session = LoginSession.objects.get(
                    user_id=user.id,
                    jwt_token=jwt_token,
                    logout_time__isnull=True,
                    refresh_expires_at__gt=now,
                    jwt_expires_at__gt=now
                )
                with schema_context(settings.PUBLIC_SCHEMA_NAME):
                    if not Client.objects.filter(
                        user_id=GymUserOtherInfo.objects.get(user=user.id).current_gym.user_id,
                        schema_name=request.tenant_schema
                    ).exists():
                        raise AuthenticationFailed("User does not belong to the tenant.", code= status.HTTP_403_FORBIDDEN)
                request.user = user  # attach user manually
                return True
            except LoginSession.DoesNotExist:
                raise AuthenticationFailed("Login session does not exist.",code= status.HTTP_404_NOT_FOUND)
            except Exception as e:
                raise AuthenticationFailed(f"Authentication failed: {str(e)}", code= status.HTTP_500_INTERNAL_SERVER_ERROR)
            except jwt.ExpiredSignatureError:
                raise AuthenticationFailed(detail="Token has expired.", code= status.HTTP_401_UNAUTHORIZED)
            except (jwt.InvalidTokenError):
                raise NotFound(detail="Invalid token", code=status.HTTP_404_NOT_FOUND)

        else:
            raise AuthenticationFailed("Missing JWT token in cookies.", code= status.HTTP_401_UNAUTHORIZED)
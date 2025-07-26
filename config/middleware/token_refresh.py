from datetime import timedelta, datetime, timezone as dt_timezone  
from django.utils import timezone  
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken, TokenError
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from accounts.models import LoginSession
from django_tenants.utils import schema_context
from django.conf import settings
from django.http import JsonResponse
from utils.utils import get_token_via_header, get_token_via_cookies, set_cookies,  set_jwt_cookie
import os

class AutoRefreshJWTMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # # print the url being accessed with indian time zone time am pm
        # indian_time = timezone.now().astimezone(dt_timezone(timedelta(hours=5, minutes=30)))

        # print(indian_time.strftime("%Y-%m-%d %I:%M %p"), "Accessed URL:", request.path)
        # # print the method of the request
        # print(indian_time.strftime("%Y-%m-%d %I:%M %p"), "Request Method:", request.method)
        # # print the headers of the request
        # print(indian_time.strftime("%Y-%m-%d %I:%M %p"), "Request Headers:", request.headers)
        # # print the host of the request
        # print(indian_time.strftime("%Y-%m-%d %I:%M %p"), "Request Host:", request.get_host())
        # # print the full path of the request
        # print(indian_time.strftime("%Y-%m-%d %I:%M %p"), "Request Full Path:", request.get_full_path())
        # # print the user agent of the request
        # print(indian_time.strftime("%Y-%m-%d %I:%M %p"), "User Agent:", request.META.get('HTTP_USER_AGENT', 'Unknown'))
        # # print the remote address of the request
        # print(indian_time.strftime("%Y-%m-%d %I:%M %p"), "Remote Address:", request.META.get('REMOTE_ADDR', 'Unknown'))
        # # print all the cookies
        # print(indian_time.strftime("%Y-%m-%d %I:%M %p"), "Cookies:", request.COOKIES)
        # jwt_token = get_token_via_cookies(request)       
        jwt_token  = get_token_via_header(request)
        # refresh_token = request.COOKIES.get('refresh_token')
        with schema_context(settings.PUBLIC_SCHEMA_NAME):
            refresh_token = LoginSession.objects.filter(
                user_id=request.user.id,
                jwt_token=jwt_token
            ).values_list('refresh_token', flat=True).first()  

        if not jwt_token:
            return

        try:
            access_token = AccessToken(jwt_token)
            user_id = access_token['user_id']
            user = get_user_model().objects.get(id=user_id)

            expires_at = access_token['exp']
            expires_at_dt = datetime.fromtimestamp(expires_at, tz=dt_timezone.utc)
            time_remaining = expires_at_dt - datetime.now(dt_timezone.utc)
            if time_remaining < timedelta(minutes=settings.JWT_REFRESH_THRESHOLD_MINUTES):  # 55 minutes window
                refresh_obj = RefreshToken(refresh_token)
                new_access_token = refresh_obj.access_token
                request.new_access_token = str(new_access_token)
                request.user = user

                # Update LoginSession inside correct tenant schema
                with schema_context(user.tenant.schema_name):
                    if not LoginSession.objects.filter(
                        user=user,
                        refresh_token=refresh_token
                    ).exists():
                        raise TokenError("Invalid session or refresh token.")
                    LoginSession.objects.filter(
                        user=user,
                        refresh_token=refresh_token
                    ).update(
                        jwt_token=str(new_access_token),
                        jwt_expires_at=datetime.now(dt_timezone.utc) + timedelta(hours=settings.JWT_TOKEN_EXPIRY_HOURS),
                        jwt_created_at=datetime.now(dt_timezone.utc),
                    )
                      
            else:
                request.user = user  # still valid, assign user

        except Exception as e:
            print(f"Token processing error: {str(e)}")
            return JsonResponse({"detail": "Unauthorized"}, status=401)


    def process_response(self, request, response):
        if hasattr(request, 'new_access_token'):
            set_jwt_cookie(response, request.new_access_token, domain=request.get_host())
        return response

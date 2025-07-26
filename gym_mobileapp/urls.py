from django.urls import path
from gym_mobileapp.views import PasswordUpdateView, LoginView, LogoutView,CustomTokenRefreshView, PunchInAPIView, PunchOutAPIView, AttendanceListAPIView,UserProfileAPIView, GymProfileView, TrainerProfileAPIView
 
urlpatterns = [
    path('gymUser/login/', LoginView.as_view()),
    path('gymUser/logout/', LogoutView.as_view()),
    path('gymUser/api/token/refresh/', CustomTokenRefreshView.as_view(), name='custom-token-refresh'),
    path('gymUser/password/update/', PasswordUpdateView.as_view(), name='update_password'),
    path('gymUser/attendance/punch-in/', PunchInAPIView.as_view(), name='punch-in'),
    path('gymUser/attendance/punch-out/', PunchOutAPIView.as_view(), name='punch-out'),
    path('gymUser/attendance/list/', AttendanceListAPIView.as_view(), name='attendance-list'),
    path('gymUser/profile/', UserProfileAPIView.as_view(), name='user-profile'),
    path('gymUser/gym-profile/', GymProfileView.as_view(), name='gym-profile'),
    path('gymUser/trainer-profile/', TrainerProfileAPIView.as_view(), name='trainer-profile'),

]

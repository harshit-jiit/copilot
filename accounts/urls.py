from django.urls import path
from .views import ActiveGymMembersView, AddGymMemberView, GymPackageCreateAPIView, GymPackageListAPIView, LoginView, LogoutView,CustomTokenRefreshView, AddGymTrainerView, ActiveGymTrainersView, GymActivityCreateAPIView, GymActivityListAPIView, GymActivityTypeCreateAPIView, GymActivityTypeListAPIView, GymActivityTypeDeleteAPIView, CheckAuthenticatedView, PaymentCreateAPIView, PaymentUpdateAPIView, PaymentDeleteAPIView, PaymentListAPIView,DashboardAPIView
 
urlpatterns = [
    path('login/', LoginView.as_view()),
    path('logout/', LogoutView.as_view()),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='custom-token-refresh'),
        # Add a new gym package (only for authenticated gym owners/admins)
    path('gym/package/add/', GymPackageCreateAPIView.as_view(), name='add_gym_package'),

    # View list of all package IDs for the current gym
    path('gym/packages/', GymPackageListAPIView.as_view(), name='gym_package_list'),

    # Add a new gym member (gym_user) and create membership entry
    path('gym/member/add/', AddGymMemberView.as_view(), name='add_gym_member'),

    # View all active members of the current gym
    path('gym/members/active/', ActiveGymMembersView.as_view(), name='active_gym_members'),

    # Add a new gym activity (only for authenticated gym owners/admins)
    path('gym/activity/add/', GymActivityCreateAPIView.as_view(), name='add_gym_activity'),

    # View list of all gym activities for the current gym
    path('gym/activities/', GymActivityListAPIView.as_view(), name='gym_activity_list'),

    # Add a new gym trainer (only for authenticated gym owners/admins)
    path('gym/trainer/add/', AddGymTrainerView.as_view(), name='add_gym_trainer'),

    # View list of all active gym trainers for the current gym
    path('gym/trainers/active/', ActiveGymTrainersView.as_view(), name='active_gym_trainers'),

    # Create a new gym activity type (only for authenticated gym owners/admins)
    path('gym/activity/type/add/', GymActivityTypeCreateAPIView.as_view(), name='add_gym_activity_type'),

    # View list of all gym activity types
    path('gym/activity/types/', GymActivityTypeListAPIView.as_view(), name='gym_activity_type_list'),
    path('gym/activity/type/delete/', GymActivityTypeDeleteAPIView.as_view(), name='delete_gym_activity_type'),

    path('gym/check-authenticated/', CheckAuthenticatedView.as_view(), name='check_authenticated'),

    # Payment-related endpoints
    path('gym/payment/create/', PaymentCreateAPIView.as_view(), name='payment_create'),
    path('gym/payment/update/', PaymentUpdateAPIView.as_view(), name='payment_update'),
    path('gym/payment/delete/', PaymentDeleteAPIView.as_view(), name='payment_delete'),
    path('gym/payment/list/', PaymentListAPIView.as_view(), name='payment_list'),
    path('gym/dashboard/', DashboardAPIView.as_view(), name='dashboard'),

]

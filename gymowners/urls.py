from django.urls import path
from .views import GymOwnerRegistrationView,HealthCheckView

urlpatterns = [
    path('register/', GymOwnerRegistrationView.as_view(), name='gymowner-register'),
    path('health/', HealthCheckView.as_view(), name='health-check'),

]

# add media url patterns
from django.conf import settings
from django.conf.urls.static import static
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
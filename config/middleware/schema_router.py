from django.http import HttpResponseBadRequest
from django.utils.deprecation import MiddlewareMixin
from gymowners.models import Domain
from django_tenants.utils import schema_context
from functools import wraps
class SchemaRoutingMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        mode = getattr(view_func, 'schema_mode', 'tenant')  # Default to tenant
        hostname = request.get_host().split(':')[0]

        if mode == 'public':
            request.tenant_schema = 'public'
        else:
            try:
                domain = Domain.objects.select_related('tenant').get(domain=hostname, is_primary=True)
                request.tenant_schema = domain.tenant.schema_name
            except Domain.DoesNotExist:
                return HttpResponseBadRequest(f"Invalid tenant: {hostname}")

        # Instead of returning the wrapped view, execute it here and return its response
        with schema_context(request.tenant_schema):
            return view_func(request, *view_args, **view_kwargs)

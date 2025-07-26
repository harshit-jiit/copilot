from django.contrib import admin

from gymowners.models import Client, Domain, CustomUser

# Register your models here.

admin.site.site_header = "Fitometer Admin"
admin.site.site_title = "Fitometer Admin Portal"
admin.site.index_title = "Welcome to Fitometer Admin Portal"
admin.site.register(Client)
admin.site.register(Domain)
admin.site.register(CustomUser)
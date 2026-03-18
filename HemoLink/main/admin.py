from django.contrib import admin
from .models import BloodRequest, DonationMatch, DonorProfile, InboxNotification, RequesterOrganization, UserProfile


admin.site.register(UserProfile)
admin.site.register(DonorProfile)
admin.site.register(RequesterOrganization)
admin.site.register(BloodRequest)
admin.site.register(DonationMatch)
admin.site.register(InboxNotification)

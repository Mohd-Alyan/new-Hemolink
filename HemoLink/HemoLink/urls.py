"""
URL configuration for HemoLink project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from main import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('about-us/', views.aboutus, name='aboutus'),
    path('emergency/', views.emergency_menu, name='emergency_menu'),
    path('emergency/live-map/', views.emergency_live_map, name='emergency_live_map'),
    path('emergency/request/', views.emergency_request, name='emergency_request'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('donor-dashboard/', views.donordashboard, name='donordashboard'),
    path('donor-availability/', views.toggle_donor_availability, name='toggle_donor_availability'),
    path('donor-locator/', views.donor_locator, name='donor_locator'),
    path('donor-requests/', views.donor_requests, name='donor_requests'),
    path('donor-inbox/', views.donor_inbox, name='donor_inbox'),
    path('requestor-dashboard/', views.requestordashboard, name='requestordashboard'),
    path('requestor-donor-network/', views.requester_donor_network, name='requester_donor_network'),
    path('requestor-status-tracking/', views.requester_status_tracking, name='requester_status_tracking'),
    path('requestor-inbox/', views.requester_inbox, name='requester_inbox'),
    path('requests/create/', views.create_blood_request, name='create_blood_request'),
    path('requests/<int:request_id>/respond/', views.respond_match, name='respond_match'),
    path('matches/<int:match_id>/select/', views.select_donor, name='select_donor'),
    path('requests/<int:request_id>/fulfilled/', views.mark_request_fulfilled, name='mark_request_fulfilled'),
    path('soon/', views.soon, name='soon'),
]

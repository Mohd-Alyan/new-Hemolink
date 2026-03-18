from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import BloodRequest, DonationMatch, DonorProfile, InboxNotification, MatchStatus, RequestStatus, RequesterOrganization, UserProfile, UserRole


DONOR_COMPATIBILITY = {
    "O-": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    "O+": ["O+", "A+", "B+", "AB+"],
    "A-": ["A-", "A+", "AB-", "AB+"],
    "A+": ["A+", "AB+"],
    "B-": ["B-", "B+", "AB-", "AB+"],
    "B+": ["B+", "AB+"],
    "AB-": ["AB-", "AB+"],
    "AB+": ["AB+"],
}


def _distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _locator_data_for_profile(profile):
    donor_lat = float(profile.latitude) if profile.latitude is not None else None
    donor_lng = float(profile.longitude) if profile.longitude is not None else None
    organizations = []
    org_qs = RequesterOrganization.objects.select_related("user_profile__user").exclude(
        user_profile__latitude__isnull=True,
    ).exclude(
        user_profile__longitude__isnull=True,
    )
    for org in org_qs:
        lat = float(org.user_profile.latitude)
        lng = float(org.user_profile.longitude)
        distance_km = _distance_km(donor_lat, donor_lng, lat, lng) if donor_lat is not None and donor_lng is not None else None
        organizations.append(
            {
                "id": org.id,
                "name": org.organization_name,
                "type": org.get_organization_type_display(),
                "phone": org.user_profile.phone_number or "N/A",
                "email": org.user_profile.user.email or "N/A",
                "latitude": lat,
                "longitude": lng,
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
            }
        )
    organizations.sort(key=lambda x: x["distance_km"] if x["distance_km"] is not None else 999999)
    if donor_lat is not None and donor_lng is not None:
        center = {"lat": donor_lat, "lng": donor_lng}
    elif organizations:
        center = {"lat": organizations[0]["latitude"], "lng": organizations[0]["longitude"]}
    else:
        center = {"lat": 20.5937, "lng": 78.9629}
    return organizations, center


def _online_eligible_donors():
    today = timezone.now().date()
    donors = []
    donor_qs = DonorProfile.objects.select_related("user_profile__user").filter(
        is_available=True,
        user_profile__latitude__isnull=False,
        user_profile__longitude__isnull=False,
    )
    for donor in donor_qs:
        if donor.last_donation_date and today < donor.last_donation_date + timedelta(days=56):
            continue
        donors.append(
            {
                "id": donor.id,
                "full_name": donor.full_name,
                "blood_type": donor.blood_type,
                "age": donor.age,
                "weight_kg": donor.weight_kg,
                "phone": donor.user_profile.phone_number or "N/A",
                "email": donor.user_profile.user.email or "N/A",
                "latitude": float(donor.user_profile.latitude),
                "longitude": float(donor.user_profile.longitude),
            }
        )
    return donors


def _donor_network_data_for_requester(profile):
    requester_lat = float(profile.latitude) if profile.latitude is not None else None
    requester_lng = float(profile.longitude) if profile.longitude is not None else None
    donors = _online_eligible_donors()
    for donor in donors:
        distance_km = _distance_km(requester_lat, requester_lng, donor["latitude"], donor["longitude"]) if requester_lat is not None and requester_lng is not None else None
        donor["distance_km"] = round(distance_km, 2) if distance_km is not None else None
    donors.sort(key=lambda x: x["distance_km"] if x["distance_km"] is not None else 999999)
    if requester_lat is not None and requester_lng is not None:
        center = {"lat": requester_lat, "lng": requester_lng}
    elif donors:
        center = {"lat": donors[0]["latitude"], "lng": donors[0]["longitude"]}
    else:
        center = {"lat": 20.5937, "lng": 78.9629}
    return donors, center


def home(request):
    registered_donors_count = DonorProfile.objects.count()
    lives_saved_count = DonationMatch.objects.filter(
        status=MatchStatus.COMPLETED,
        blood_request__fulfilled_at__isnull=False,
    ).count()
    linked_organizations_count = RequesterOrganization.objects.count()
    return render(
        request,
        "main/home.html",
        {
            "registered_donors_count": registered_donors_count,
            "lives_saved_count": lives_saved_count,
            "linked_organizations_count": linked_organizations_count,
        },
    )


def aboutus(request):
    return render(request, "main/aboutus.html")


def emergency_menu(request):
    return render(request, "main/emergency_menu.html")


def emergency_live_map(request):
    lat_param = request.GET.get("lat")
    lng_param = request.GET.get("lng")
    try:
        center_lat = float(lat_param) if lat_param else None
        center_lng = float(lng_param) if lng_param else None
    except (TypeError, ValueError):
        center_lat = None
        center_lng = None
    donors = _online_eligible_donors()
    for donor in donors:
        distance_km = _distance_km(center_lat, center_lng, donor["latitude"], donor["longitude"]) if center_lat is not None and center_lng is not None else None
        donor["distance_km"] = round(distance_km, 2) if distance_km is not None else None
    donors.sort(key=lambda x: x["distance_km"] if x["distance_km"] is not None else 999999)
    if center_lat is not None and center_lng is not None:
        center = {"lat": center_lat, "lng": center_lng}
    elif donors:
        center = {"lat": donors[0]["latitude"], "lng": donors[0]["longitude"]}
    else:
        center = {"lat": 20.5937, "lng": 78.9629}
    return render(request, "main/emergency_live_map.html", {"donor_locations": donors, "map_center": center})


def emergency_request(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        blood_type = request.POST.get("blood_type", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone_number", "").strip()
        latitude = request.POST.get("latitude", "").strip()
        longitude = request.POST.get("longitude", "").strip()
        if not name or not blood_type or not email or not phone:
            return render(request, "main/emergency_request_form.html", {"error": "Please fill all required fields."})
        location_text = f"{latitude}, {longitude}" if latitude and longitude else "Location not provided"
        urgent_message = (
            f"URGENT: {name} needs {blood_type} blood. "
            f"Contact: {phone}, {email}. Location: {location_text}."
        )
        users_to_notify = User.objects.filter(profile__role__in=[UserRole.DONOR, UserRole.REQUESTER]).distinct()
        InboxNotification.objects.bulk_create([InboxNotification(user=user, message=urgent_message) for user in users_to_notify])
        messages.success(request, "Emergency request sent to all donors and organizations.")
        return redirect("emergency_menu")
    return render(request, "main/emergency_request_form.html")


def login_view(request):
    if request.method == "POST":
        identifier = request.POST.get("identifier", "").strip()
        password = request.POST.get("password", "")
        username = identifier
        if "@" not in identifier:
            profile = UserProfile.objects.select_related("user").filter(phone_number=identifier).first()
            if profile:
                username = profile.user.username
        user = authenticate(request, username=username, password=password)
        if not user:
            return render(request, "main/login.html", {"error": "Invalid credentials."})
        auth_login(request, user)
        if hasattr(user, "profile") and user.profile.role == UserRole.REQUESTER:
            return redirect("requestordashboard")
        return redirect("donordashboard")
    return render(request, "main/login.html")


def register(request):
    if request.method == "POST":
        role = request.POST.get("role", UserRole.DONOR)
        if role not in {UserRole.DONOR, UserRole.REQUESTER}:
            role = UserRole.DONOR
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone_number", "").strip()
        latitude = request.POST.get("latitude")
        longitude = request.POST.get("longitude")
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not email or not password:
            return render(request, "main/register.html", {"error": "Email and password are required."})
        if password != confirm_password:
            return render(request, "main/register.html", {"error": "Passwords do not match."})
        if User.objects.filter(username=email).exists():
            return render(request, "main/register.html", {"error": "An account with this email already exists."})
        if role == UserRole.REQUESTER and (
            not request.POST.get("organization_name", "").strip() or not request.POST.get("organization_type", "").strip()
        ):
            return render(request, "main/register.html", {"error": "Organization details are required."})
        if role == UserRole.DONOR and (
            not request.POST.get("full_name", "").strip()
            or not request.POST.get("blood_type", "").strip()
            or not request.POST.get("date_of_birth")
            or not request.POST.get("weight_kg")
            or not request.POST.get("gender", "").strip()
        ):
            return render(request, "main/register.html", {"error": "Donor profile details are required."})

        with transaction.atomic():
            user = User.objects.create_user(username=email, email=email, password=password)
            profile = UserProfile.objects.create(
                user=user,
                role=role,
                phone_number=phone,
                latitude=latitude or None,
                longitude=longitude or None,
            )
            if role == UserRole.REQUESTER:
                RequesterOrganization.objects.create(
                    user_profile=profile,
                    organization_name=request.POST.get("organization_name", "").strip(),
                    organization_type=request.POST.get("organization_type", "").strip(),
                )
                redirect_name = "requestordashboard"
            else:
                DonorProfile.objects.create(
                    user_profile=profile,
                    full_name=request.POST.get("full_name", "").strip(),
                    blood_type=request.POST.get("blood_type", "").strip(),
                    date_of_birth=request.POST.get("date_of_birth"),
                    weight_kg=request.POST.get("weight_kg"),
                    gender=request.POST.get("gender", "").strip(),
                )
                redirect_name = "donordashboard"

        auth_login(request, user)
        return redirect(redirect_name)

    return render(request, "main/register.html")


def donordashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")
    profile = getattr(request.user, "profile", None)
    if not profile or profile.role != UserRole.DONOR:
        return redirect("requestordashboard")
    donor = getattr(profile, "donor_profile", None)
    if not donor:
        messages.error(request, "Donor profile is missing.")
        return redirect("register")

    today = timezone.now().date()
    next_eligible_date = donor.last_donation_date + timedelta(days=56) if donor.last_donation_date else None
    eligible_now = not next_eligible_date or today >= next_eligible_date

    compatible_request_types = DONOR_COMPATIBILITY.get(donor.blood_type, [donor.blood_type])
    open_requests = (
        BloodRequest.objects.select_related("requester")
        .filter(status__in=[RequestStatus.OPEN, RequestStatus.MATCHED], blood_type__in=compatible_request_types)
        .order_by("-created_at")
    )
    selected_map = {
        m.blood_request_id: m.donor_id
        for m in DonationMatch.objects.filter(
            blood_request__in=open_requests,
            is_selected=True,
        ).only("blood_request_id", "donor_id")
    }
    open_requests = [req for req in open_requests if req.id not in selected_map]
    match_map = {
        m.blood_request_id: m.status
        for m in DonationMatch.objects.filter(donor=donor, blood_request__in=open_requests)
    }
    request_cards = [{"request": blood_request, "match_status": match_map.get(blood_request.id)} for blood_request in open_requests]
    completed_matches = DonationMatch.objects.select_related("blood_request__requester").filter(
        donor=donor,
        status=MatchStatus.COMPLETED,
        blood_request__fulfilled_at__isnull=False,
    ).order_by("-blood_request__fulfilled_at")
    recent_activities = completed_matches[:5]
    lives_saved_count = completed_matches.count()
    org_locations, map_center = _locator_data_for_profile(profile)
    return render(
        request,
        "main/donordashboard.html",
        {
            "request_cards": request_cards,
            "user_profile": profile,
            "donor_profile": donor,
            "eligible_now": eligible_now,
            "next_eligible_date": next_eligible_date,
            "recent_activities": recent_activities,
            "lives_saved_count": lives_saved_count,
            "org_locations": org_locations,
            "map_center": map_center,
            "donor_online": donor.is_available,
        },
    )


def requestordashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")
    profile = getattr(request.user, "profile", None)
    if not profile or profile.role != UserRole.REQUESTER:
        return redirect("donordashboard")
    organization = getattr(profile, "requester_organization", None)
    if not organization:
        messages.error(request, "Requester organization profile is missing.")
        return redirect("register")

    blood_requests = list(organization.blood_requests.order_by("-created_at"))
    network_donors, network_center = _donor_network_data_for_requester(profile)
    return render(
        request,
        "main/requestordashboard.html",
        {
            "blood_requests": blood_requests,
            "user_profile": profile,
            "requester_org": organization,
            "nearest_donors": network_donors[:5],
            "network_donors": network_donors,
            "network_center": network_center,
        },
    )


@login_required
def donor_requests(request):
    profile = getattr(request.user, "profile", None)
    if not profile or profile.role != UserRole.DONOR:
        return redirect("requestordashboard")
    donor = getattr(profile, "donor_profile", None)
    assigned_matches = (
        DonationMatch.objects.select_related("blood_request__requester__user_profile")
        .filter(donor=donor, is_selected=True)
        .order_by("-selected_at")
    )
    return render(
        request,
        "main/donor_requests.html",
        {"user_profile": profile, "donor_profile": donor, "assigned_matches": assigned_matches},
    )


@login_required
def donor_inbox(request):
    profile = getattr(request.user, "profile", None)
    if not profile or profile.role != UserRole.DONOR:
        return redirect("requestordashboard")
    donor = getattr(profile, "donor_profile", None)
    inbox_notifications = request.user.inbox_notifications.all()[:30]
    return render(
        request,
        "main/donor_inbox.html",
        {"user_profile": profile, "donor_profile": donor, "inbox_notifications": inbox_notifications},
    )


@login_required
def donor_locator(request):
    profile = getattr(request.user, "profile", None)
    if not profile or profile.role != UserRole.DONOR:
        return redirect("requestordashboard")
    donor = getattr(profile, "donor_profile", None)
    organizations, map_center = _locator_data_for_profile(profile)
    return render(
        request,
        "main/donor_locator.html",
        {
            "user_profile": profile,
            "donor_profile": donor,
            "org_locations": organizations,
            "map_center": map_center,
        },
    )


@login_required
def requester_donor_network(request):
    profile = getattr(request.user, "profile", None)
    if not profile or profile.role != UserRole.REQUESTER:
        return redirect("donordashboard")
    organization = getattr(profile, "requester_organization", None)
    if not organization:
        messages.error(request, "Requester organization profile is missing.")
        return redirect("register")
    donors, map_center = _donor_network_data_for_requester(profile)
    return render(
        request,
        "main/requester_donor_network.html",
        {
            "user_profile": profile,
            "requester_org": organization,
            "donor_locations": donors,
            "map_center": map_center,
        },
    )


@login_required
def requester_status_tracking(request):
    profile = getattr(request.user, "profile", None)
    if not profile or profile.role != UserRole.REQUESTER:
        return redirect("donordashboard")
    organization = getattr(profile, "requester_organization", None)
    blood_requests = list(organization.blood_requests.order_by("-created_at"))
    accepted_matches = (
        DonationMatch.objects.select_related("donor__user_profile", "blood_request")
        .filter(blood_request__requester=organization, status=MatchStatus.ACCEPTED)
        .order_by("-responded_at")
    )
    status_tracking = {}
    for match in accepted_matches:
        status_tracking.setdefault(match.blood_request_id, []).append(match)
    status_rows = [{"request": req, "matches": status_tracking.get(req.id, [])} for req in blood_requests]
    return render(
        request,
        "main/requester_status_tracking.html",
        {"user_profile": profile, "requester_org": organization, "status_rows": status_rows},
    )


@login_required
def requester_inbox(request):
    profile = getattr(request.user, "profile", None)
    if not profile or profile.role != UserRole.REQUESTER:
        return redirect("donordashboard")
    organization = getattr(profile, "requester_organization", None)
    inbox_notifications = request.user.inbox_notifications.all()[:30]
    return render(
        request,
        "main/requester_inbox.html",
        {"user_profile": profile, "requester_org": organization, "inbox_notifications": inbox_notifications},
    )


@login_required
def create_blood_request(request):
    profile = getattr(request.user, "profile", None)
    if request.method != "POST" or not profile or profile.role != UserRole.REQUESTER:
        return redirect("requestordashboard")

    organization = getattr(profile, "requester_organization", None)
    if not organization:
        messages.error(request, "Requester organization profile is missing.")
        return redirect("register")

    blood_type = request.POST.get("blood_type", "").strip()
    units_required = request.POST.get("units_required")
    priority = request.POST.get("priority", "normal").strip()
    notes = request.POST.get("notes", "").strip()
    if not blood_type or not units_required:
        messages.error(request, "Blood type and units are required.")
        return redirect("requestordashboard")

    BloodRequest.objects.create(
        requester=organization,
        blood_type=blood_type,
        units_required=units_required,
        priority=priority,
        notes=notes,
    )
    messages.success(request, "Blood request created.")
    return redirect("requestordashboard")


@login_required
def respond_match(request, request_id):
    profile = getattr(request.user, "profile", None)
    if request.method != "POST" or not profile or profile.role != UserRole.DONOR:
        return redirect("donordashboard")
    donor = getattr(profile, "donor_profile", None)
    if not donor:
        messages.error(request, "Donor profile is missing.")
        return redirect("register")

    today = timezone.now().date()
    next_eligible_date = donor.last_donation_date + timedelta(days=56) if donor.last_donation_date else None
    if next_eligible_date and today < next_eligible_date:
        messages.error(request, f"You can donate again on {next_eligible_date}.")
        return redirect("donordashboard")

    blood_request = get_object_or_404(BloodRequest, id=request_id)
    if DonationMatch.objects.filter(blood_request=blood_request, is_selected=True).exclude(donor=donor).exists():
        messages.error(request, "A donor has already been selected for this request.")
        return redirect("donordashboard")
    action = request.POST.get("action")
    status = MatchStatus.ACCEPTED if action == "accept" else MatchStatus.DECLINED
    match, _ = DonationMatch.objects.get_or_create(
        blood_request=blood_request,
        donor=donor,
        defaults={"status": status, "responded_at": timezone.now()},
    )
    if match.status != status:
        match.status = status
        match.responded_at = timezone.now()
        match.save(update_fields=["status", "responded_at"])
    if status == MatchStatus.ACCEPTED and blood_request.status == RequestStatus.OPEN:
        blood_request.status = RequestStatus.MATCHED
        blood_request.save(update_fields=["status"])
        InboxNotification.objects.create(
            user=blood_request.requester.user_profile.user,
            blood_request=blood_request,
            message=f"{donor.full_name} accepted Request #{blood_request.id}.",
        )
    elif status == MatchStatus.ACCEPTED:
        InboxNotification.objects.create(
            user=blood_request.requester.user_profile.user,
            blood_request=blood_request,
            message=f"{donor.full_name} accepted Request #{blood_request.id}.",
        )
    messages.success(request, "Response submitted.")
    return redirect("donordashboard")


@login_required
def mark_request_fulfilled(request, request_id):
    profile = getattr(request.user, "profile", None)
    if request.method != "POST" or not profile or profile.role != UserRole.REQUESTER:
        return redirect("requestordashboard")
    organization = getattr(profile, "requester_organization", None)
    blood_request = get_object_or_404(BloodRequest, id=request_id, requester=organization)
    blood_request.status = RequestStatus.FULFILLED
    blood_request.fulfilled_at = timezone.now()
    blood_request.save(update_fields=["status", "fulfilled_at"])
    selected_match = DonationMatch.objects.select_related("donor").filter(
        blood_request=blood_request,
        is_selected=True,
    ).first()
    if selected_match:
        selected_match.status = MatchStatus.COMPLETED
        selected_match.responded_at = timezone.now()
        selected_match.save(update_fields=["status", "responded_at"])
        donor = selected_match.donor
        donor.last_donation_date = blood_request.fulfilled_at.date()
        donor.save(update_fields=["last_donation_date"])
    messages.success(request, "Request marked as fulfilled.")
    return redirect("requestordashboard")


@login_required
def select_donor(request, match_id):
    profile = getattr(request.user, "profile", None)
    if request.method != "POST" or not profile or profile.role != UserRole.REQUESTER:
        return redirect("requestordashboard")
    organization = getattr(profile, "requester_organization", None)
    match = get_object_or_404(
        DonationMatch.objects.select_related("blood_request", "donor__user_profile"),
        id=match_id,
        blood_request__requester=organization,
        status=MatchStatus.ACCEPTED,
    )
    DonationMatch.objects.filter(blood_request=match.blood_request).update(is_selected=False, selected_at=None)
    match.is_selected = True
    match.selected_at = timezone.now()
    match.save(update_fields=["is_selected", "selected_at"])
    InboxNotification.objects.create(
        user=match.donor.user_profile.user,
        blood_request=match.blood_request,
        message=f"You were selected by {organization.organization_name} for Request #{match.blood_request.id}.",
    )
    messages.success(request, "Donor selected and notified.")
    return redirect("requestordashboard")


@login_required
def logout_view(request):
    auth_logout(request)
    return redirect("home")


@login_required
def toggle_donor_availability(request):
    profile = getattr(request.user, "profile", None)
    if request.method != "POST" or not profile or profile.role != UserRole.DONOR:
        return redirect("donordashboard")
    donor = getattr(profile, "donor_profile", None)
    if not donor:
        messages.error(request, "Donor profile is missing.")
        return redirect("register")
    donor.is_available = not donor.is_available
    donor.save(update_fields=["is_available"])
    messages.success(request, f"You are now {'online' if donor.is_available else 'offline'}.")
    return redirect("donordashboard")

def soon(request):
    return render(request, "main/soon.html")
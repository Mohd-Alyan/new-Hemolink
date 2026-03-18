from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from main.models import OrganizationType, RequesterOrganization, UserProfile, UserRole


class Command(BaseCommand):
    help = "Seed 6 hospitals and 4 blood banks near a donor's saved coordinates."

    def handle(self, *args, **options):
        anchor = (
            UserProfile.objects.filter(
                role=UserRole.DONOR,
                latitude__isnull=False,
                longitude__isnull=False,
            )
            .order_by("id")
            .first()
        )
        if not anchor:
            self.stdout.write(self.style.ERROR("No donor with saved coordinates found. Register a donor with location first."))
            return

        base_lat = float(anchor.latitude)
        base_lng = float(anchor.longitude)
        demo_orgs = [
            ("Apex City Hospital", OrganizationType.HOSPITAL, "+91-9000000001", "apex.hospital.demo@hemo.test", 0.0080, 0.0040),
            ("Metro General Hospital", OrganizationType.HOSPITAL, "+91-9000000002", "metro.hospital.demo@hemo.test", -0.0070, 0.0060),
            ("Sunrise Trauma Center", OrganizationType.HOSPITAL, "+91-9000000003", "sunrise.hospital.demo@hemo.test", 0.0120, -0.0035),
            ("Greenlife Medical Center", OrganizationType.HOSPITAL, "+91-9000000004", "greenlife.hospital.demo@hemo.test", -0.0105, -0.0050),
            ("Riverfront Hospital", OrganizationType.HOSPITAL, "+91-9000000005", "riverfront.hospital.demo@hemo.test", 0.0150, 0.0080),
            ("Northpoint Care Hospital", OrganizationType.HOSPITAL, "+91-9000000006", "northpoint.hospital.demo@hemo.test", -0.0130, 0.0090),
            ("Lifeline Blood Bank", OrganizationType.BLOOD_BANK, "+91-9000000101", "lifeline.bloodbank.demo@hemo.test", 0.0040, -0.0100),
            ("RedCross Community Blood Bank", OrganizationType.BLOOD_BANK, "+91-9000000102", "redcross.bloodbank.demo@hemo.test", -0.0050, -0.0110),
            ("Hope Plasma & Blood Center", OrganizationType.BLOOD_BANK, "+91-9000000103", "hope.bloodbank.demo@hemo.test", 0.0100, 0.0120),
            ("Unity Regional Blood Bank", OrganizationType.BLOOD_BANK, "+91-9000000104", "unity.bloodbank.demo@hemo.test", -0.0090, 0.0130),
        ]

        created = 0
        updated = 0

        with transaction.atomic():
            for name, org_type, phone, email, dlat, dlng in demo_orgs:
                user, user_created = User.objects.get_or_create(
                    username=email,
                    defaults={"email": email},
                )
                if user_created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])

                profile, profile_created = UserProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "role": UserRole.REQUESTER,
                        "phone_number": phone,
                        "latitude": round(base_lat + dlat, 6),
                        "longitude": round(base_lng + dlng, 6),
                    },
                )
                RequesterOrganization.objects.update_or_create(
                    user_profile=profile,
                    defaults={
                        "organization_name": name,
                        "organization_type": org_type,
                    },
                )

                if user_created or profile_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f"Seed complete. Created/updated {created + updated} organizations near donor location."))

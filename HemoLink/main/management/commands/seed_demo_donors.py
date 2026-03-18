from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from main.models import BloodType, DonorProfile, UserProfile, UserRole


class Command(BaseCommand):
    help = "Seed fake donors around a saved user location."

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, help="Center seed around this user's saved coordinates.")

    def handle(self, *args, **options):
        center_email = options.get("email")
        if center_email:
            anchor = UserProfile.objects.filter(
                user__email=center_email,
                latitude__isnull=False,
                longitude__isnull=False,
            ).first()
        else:
            anchor = (
                UserProfile.objects.filter(latitude__isnull=False, longitude__isnull=False)
                .order_by("id")
                .first()
            )

        if not anchor:
            self.stdout.write(self.style.ERROR("No user with saved coordinates found. Register with location first."))
            return

        base_lat = float(anchor.latitude)
        base_lng = float(anchor.longitude)

        demo_donors = [
            ("Arjun Mehta", BloodType.O_POS, "Male", date(1998, 5, 11), 72.4, "+91-9001001001", 0.0042, 0.0031),
            ("Nisha Verma", BloodType.A_POS, "Female", date(2000, 9, 2), 58.2, "+91-9001001002", -0.0035, 0.0054),
            ("Rahul Khanna", BloodType.B_NEG, "Male", date(1995, 1, 19), 76.0, "+91-9001001003", 0.0070, -0.0028),
            ("Priya Nair", BloodType.O_NEG, "Female", date(1997, 12, 7), 61.3, "+91-9001001004", -0.0058, -0.0045),
            ("Aman Sethi", BloodType.AB_POS, "Male", date(1999, 3, 27), 69.1, "+91-9001001005", 0.0091, 0.0018),
            ("Sana Iqbal", BloodType.B_POS, "Female", date(2001, 6, 15), 55.7, "+91-9001001006", -0.0082, 0.0062),
            ("Dev Malhotra", BloodType.A_NEG, "Male", date(1996, 10, 29), 74.8, "+91-9001001007", 0.0024, -0.0077),
            ("Kriti Sharma", BloodType.AB_NEG, "Female", date(1994, 8, 9), 59.6, "+91-9001001008", -0.0095, -0.0031),
            ("Yash Jain", BloodType.O_POS, "Male", date(2002, 2, 3), 67.2, "+91-9001001009", 0.0110, 0.0049),
            ("Meera Das", BloodType.A_POS, "Female", date(1998, 11, 22), 57.9, "+91-9001001010", -0.0019, -0.0102),
            ("Kunal Roy", BloodType.B_POS, "Male", date(1993, 4, 14), 79.0, "+91-9001001011", 0.0064, 0.0090),
            ("Ira Kapoor", BloodType.O_NEG, "Female", date(2000, 7, 30), 60.1, "+91-9001001012", -0.0108, 0.0025),
        ]

        created = 0
        updated = 0
        with transaction.atomic():
            for index, (name, blood_type, gender, dob, weight, phone, dlat, dlng) in enumerate(demo_donors, start=1):
                email = f"demo.donor{index}@hemo.test"
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
                        "role": UserRole.DONOR,
                        "phone_number": phone,
                        "latitude": round(base_lat + dlat, 6),
                        "longitude": round(base_lng + dlng, 6),
                    },
                )

                DonorProfile.objects.update_or_create(
                    user_profile=profile,
                    defaults={
                        "full_name": name,
                        "blood_type": blood_type,
                        "date_of_birth": dob,
                        "weight_kg": weight,
                        "gender": gender,
                        "is_available": True,
                        "last_donation_date": None,
                    },
                )

                if user_created or profile_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f"Seed complete. Created/updated {created + updated} fake donors near anchor location."))

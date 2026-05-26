# Generated for the QuickZaps onboarding migration.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_rename_core_apilog_user_created_idx_core_apireq_user_id_4b1e2b_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnboardingApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("requested_role", models.CharField(choices=[("SDBR", "Super Distributor"), ("DBR", "Distributor"), ("RETAILER", "Retailer")], max_length=20)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("pending_parent", "Pending Parent Approval"), ("pending_admin", "Pending Admin Approval"), ("approved", "Approved"), ("rejected", "Rejected"), ("created", "User Created")], db_index=True, default="pending_admin", max_length=30)),
                ("direct_to_admin", models.BooleanField(default=False)),
                ("mobile", models.CharField(db_index=True, max_length=20)),
                ("email", models.EmailField(max_length=254)),
                ("full_name", models.CharField(max_length=160)),
                ("dob", models.DateField()),
                ("aadhaar_number", models.CharField(max_length=20)),
                ("pan_number", models.CharField(max_length=20)),
                ("pan_verification", models.JSONField(blank=True, default=dict)),
                ("aadhaar_verification", models.JSONField(blank=True, default=dict)),
                ("bank_verification", models.JSONField(blank=True, default=dict)),
                ("gst_verification", models.JSONField(blank=True, default=dict)),
                ("udyam_verification", models.JSONField(blank=True, default=dict)),
                ("verification_mode", models.CharField(default="dummy", max_length=20)),
                ("live_photo", models.FileField(blank=True, null=True, upload_to="onboarding/live_photo/")),
                ("live_photo_geo", models.JSONField(blank=True, default=dict)),
                ("shop_photo", models.FileField(blank=True, null=True, upload_to="onboarding/shop_photo/")),
                ("shop_photo_geo", models.JSONField(blank=True, default=dict)),
                ("agent_photo", models.FileField(blank=True, null=True, upload_to="onboarding/agent_photo/")),
                ("agent_photo_geo", models.JSONField(blank=True, default=dict)),
                ("account_holder_name", models.CharField(max_length=160)),
                ("bank_name", models.CharField(blank=True, max_length=120)),
                ("account_number", models.CharField(max_length=40)),
                ("ifsc", models.CharField(max_length=20)),
                ("upi_id", models.CharField(blank=True, max_length=120)),
                ("bank_proof", models.FileField(blank=True, null=True, upload_to="onboarding/bank_proof/")),
                ("rpd_reference_id", models.CharField(blank=True, max_length=120)),
                ("rpd_link", models.URLField(blank=True)),
                ("rpd_status", models.CharField(blank=True, max_length=40)),
                ("business_name", models.CharField(max_length=160)),
                ("business_type", models.CharField(blank=True, max_length=80)),
                ("gst_number", models.CharField(blank=True, max_length=30)),
                ("udyam_number", models.CharField(blank=True, max_length=40)),
                ("business_address", models.TextField()),
                ("city", models.CharField(max_length=80)),
                ("state", models.CharField(max_length=80)),
                ("pin_code", models.CharField(max_length=12)),
                ("business_photo", models.FileField(blank=True, null=True, upload_to="onboarding/business_photo/")),
                ("gst_document", models.FileField(blank=True, null=True, upload_to="onboarding/gst_document/")),
                ("udyam_document", models.FileField(blank=True, null=True, upload_to="onboarding/udyam_document/")),
                ("review_note", models.TextField(blank=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("rejected_at", models.DateTimeField(blank=True, null=True)),
                ("agent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="agent_onboarding_applications", to=settings.AUTH_USER_MODEL)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_onboarding_applications", to=settings.AUTH_USER_MODEL)),
                ("created_user", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="source_onboarding_application", to=settings.AUTH_USER_MODEL)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="parent_onboarding_applications", to=settings.AUTH_USER_MODEL)),
                ("parent_approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="parent_approved_onboarding", to=settings.AUTH_USER_MODEL)),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_onboarding_applications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "requested_role"], name="core_onboar_status_f3f8b6_idx"),
                    models.Index(fields=["mobile"], name="core_onboar_mobile_535ab4_idx"),
                    models.Index(fields=["parent", "status"], name="core_onboar_parent__b9e831_idx"),
                ],
            },
        ),
    ]

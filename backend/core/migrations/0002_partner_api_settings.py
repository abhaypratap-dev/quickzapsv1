# Generated for the PostgreSQL migration target.

import core.models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PartnerAPISetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("api_key", models.CharField(db_index=True, default=core.models.generate_api_key, max_length=64, unique=True)),
                ("allowed_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("allowed_ip2", models.GenericIPAddressField(blank=True, null=True)),
                ("webhook_url", models.URLField(blank=True)),
                ("active", models.BooleanField(default=True)),
                ("generated_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "user",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="partner_api_setting", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["user__mobile"],
            },
        ),
        migrations.CreateModel(
            name="APIRequestLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("request_id", models.CharField(blank=True, db_index=True, max_length=120)),
                ("api_key_prefix", models.CharField(blank=True, max_length=16)),
                ("path", models.CharField(max_length=240)),
                ("method", models.CharField(max_length=12)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("response_payload", models.JSONField(blank=True, default=dict)),
                ("status_code", models.PositiveSmallIntegerField(default=200)),
                (
                    "user",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="api_request_logs", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["user", "created_at"], name="core_apilog_user_created_idx"),
                    models.Index(fields=["request_id"], name="core_apilog_request_idx"),
                    models.Index(fields=["status_code", "created_at"], name="core_apilog_status_idx"),
                ],
            },
        ),
    ]

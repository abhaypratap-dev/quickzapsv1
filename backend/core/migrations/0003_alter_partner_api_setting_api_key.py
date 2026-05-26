from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_partner_api_settings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="partnerapisetting",
            name="api_key",
            field=models.CharField(db_index=True, max_length=128, unique=True),
        ),
    ]
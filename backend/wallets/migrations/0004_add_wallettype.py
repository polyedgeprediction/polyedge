# Generated migration for adding wallettype field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallets', '0003_alter_walletcategorystat_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallet',
            name='wallettype',
            field=models.CharField(
                choices=[('new', 'New'), ('old', 'Old')],
                default='old',
                db_index=True,
                help_text='Wallet lifecycle status (new/old)',
                max_length=10
            ),
        ),
    ]


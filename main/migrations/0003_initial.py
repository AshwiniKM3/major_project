# Generated by Django 5.1.2 on 2024-10-25 09:44

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('main', '0002_delete_queueentry'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskExecution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.CharField(max_length=255)),
                ('status', models.CharField(max_length=50)),
                ('scheduled_time', models.DateTimeField()),
                ('actual_time', models.DateTimeField()),
                ('delay', models.FloatField()),
            ],
        ),
    ]

# Generated by Django 2.2.7 on 2024-03-13 08:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shopper', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='shoppingitem',
            name='urgent',
            field=models.CharField(choices=[('yes', 'yes'), ('no', 'no')], default='no', max_length=8),
        ),
    ]

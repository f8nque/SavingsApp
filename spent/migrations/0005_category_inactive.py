# Generated by Django 2.2.7 on 2023-04-23 08:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spent', '0004_spent_comment'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='inactive',
            field=models.IntegerField(default=0),
        ),
    ]

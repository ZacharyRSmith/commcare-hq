# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-01-02 21:22
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0011_add_broadcast_deleted_flag'),
    ]

    operations = [
        migrations.AddField(
            model_name='alertschedule',
            name='deleted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='timedschedule',
            name='deleted',
            field=models.BooleanField(default=False),
        ),
    ]

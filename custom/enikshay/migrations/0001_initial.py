# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-03-22 00:27
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='IssuerId',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=255)),
                ('user_id', models.CharField(db_index=True, max_length=50, unique=True)),
            ],
        ),
    ]

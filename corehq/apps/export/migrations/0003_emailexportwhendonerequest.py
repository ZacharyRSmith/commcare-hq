# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-01-18 15:38
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('export', '0002_datafile'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailExportWhenDoneRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255)),
                ('download_id', models.CharField(max_length=255)),
                ('user_id', models.CharField(max_length=255)),
            ],
        ),
    ]
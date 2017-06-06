# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-01 21:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('private_sector_datamigration', '0008_episodeprescription_voucher'),
    ]

    operations = [
        migrations.AlterField(
            model_name='beneficiary',
            name='firstName',
            field=models.CharField(max_length=30),
        ),
        migrations.AlterField(
            model_name='beneficiary',
            name='lastName',
            field=models.CharField(max_length=30),
        ),
        migrations.AlterField(
            model_name='beneficiary',
            name='phoneNumber',
            field=models.CharField(max_length=10),
        ),
        migrations.AlterField(
            model_name='episode',
            name='dateOfDiagnosis',
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name='episode',
            name='rxStartDate',
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name='episode',
            name='site',
            field=models.CharField(max_length=255),
        ),
    ]
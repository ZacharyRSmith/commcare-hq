# -*- coding: utf-8 -*-
# Generated by Django 1.11.10 on 2018-02-19 21:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0033_add_new_aadhaar_indicators'),
    ]

    operations = [
        migrations.CreateModel(
            name='AggregateComplementaryFeedingForms',
            fields=[
                ('state_id', models.CharField(max_length=40)),
                ('month', models.DateField(help_text=b'Will always be YYYY-MM-01')),
                ('case_id', models.CharField(max_length=40, primary_key=True, serialize=False)),
                ('latest_time_end_processed', models.DateTimeField(help_text=b'The latest form.meta.timeEnd that has been processed for this case')),
                ('comp_feeding_ever', models.PositiveSmallIntegerField(help_text=b'Complementary feeding has ever occurred for this case', null=True)),
                ('demo_comp_feeding', models.PositiveSmallIntegerField(help_text=b'Demo of complementary feeding has ever occurred', null=True)),
                ('counselled_pediatric_ifa', models.PositiveSmallIntegerField(help_text=b'Once the child is over 1 year, has ever been counseled on pediatric IFA', null=True)),
                ('play_comp_feeding_vid', models.PositiveSmallIntegerField(help_text=b'Case has ever been counseled about complementary feeding with a video', null=True)),
                ('comp_feeding_latest', models.PositiveSmallIntegerField(help_text=b'Complementary feeding occurred for this case in the latest form', null=True)),
                ('diet_diversity', models.PositiveSmallIntegerField(help_text=b'Diet diversity occurred for this case in the latest form', null=True)),
                ('diet_quantity', models.PositiveSmallIntegerField(help_text=b'Diet quantity occurred for this case in the latest form', null=True)),
                ('hand_wash', models.PositiveSmallIntegerField(help_text=b'Hand washing occurred for this case in the latest form', null=True)),
            ],
            options={
                'db_table': 'icds_dashboard_comp_feed_form',
            },
        ),
    ]
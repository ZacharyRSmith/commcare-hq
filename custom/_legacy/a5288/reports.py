from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
import pytz
from corehq.apps.hqcase.dbaccessors import get_cases_in_domain
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.sms.models import ExpectedCallback, CALLBACK_PENDING, CALLBACK_RECEIVED, CALLBACK_MISSED
from datetime import datetime, timedelta, time
from corehq.util.timezones.conversions import ServerTime
from dimagi.utils.parsing import json_format_date
from six.moves import range


class MissedCallbackReport(CustomProjectReport, GenericTabularReport):
    name = ugettext_noop("Missed Callbacks")
    slug = "missed_callbacks"
    description = ugettext_noop("Summarizes two weeks of SMS / Callback interactions for all participants.")
    flush_layout = True
    
    def get_past_two_weeks(self):
        now = datetime.utcnow()
        local_datetime = ServerTime(now).user_time(self.timezone).done()
        return [(local_datetime + timedelta(days = x)).date() for x in range(-14, 0)]
    
    @property
    def headers(self):
        args = [
            DataTablesColumn(_("Participant ID")),
            DataTablesColumn(_("Total No Response")),
            DataTablesColumn(_("Total Indicated")),
            DataTablesColumn(_("Total Pending")),
        ]
        args += [DataTablesColumn(date.strftime("%b %d")) for date in self.get_past_two_weeks()]
        return DataTablesHeader(*args)
    
    @property
    def rows(self):
        group_id = None
        if self.request.couch_user.is_commcare_user():
            group_ids = self.request.couch_user.get_group_ids()
            if len(group_ids) > 0:
                group_id = group_ids[0]

        data = {}

        for case in get_cases_in_domain(self.domain, type='participant'):
            if case.closed:
                continue

            # If a site coordinator is viewing the report, only show participants from that site (group)
            if group_id is None or group_id == case.owner_id:
                timezone = pytz.timezone(case.get_case_property("time_zone"))
                data[case._id] = {
                    "name": case.name,
                    "time_zone": timezone,
                    "dates": [None] * 14,
                }

        dates = self.get_past_two_weeks()
        date_strings = [json_format_date(date) for date in dates]

        start_date = dates[0] - timedelta(days=1)
        end_date = dates[-1] + timedelta(days=2)

        expected_callback_events = ExpectedCallback.by_domain(
            self.domain,
            start_date=datetime.combine(start_date, time(0, 0)),
            end_date=datetime.combine(end_date, time(0, 0))
        ).order_by('date')

        for event in expected_callback_events:
            if event.couch_recipient in data:
                timezone = data[event.couch_recipient]["time_zone"]
                event_date = (ServerTime(event.date).user_time(timezone)
                              .ui_string("%Y-%m-%d"))
                if event_date in date_strings:
                    data[event.couch_recipient]["dates"][date_strings.index(event_date)] = event.status

        result = []
        for case_id, data_dict in data.items():
            row = [
                self._fmt(data_dict["name"]),
                None,
                None,
                None,
            ]
            
            total_no_response = 0
            total_indicated = 0
            total_pending = 0
            
            for date_status in data_dict["dates"]:
                if date_status == CALLBACK_PENDING:
                    total_indicated += 1
                    total_pending += 1
                    row.append(self._fmt(_("pending")))
                elif date_status == CALLBACK_RECEIVED:
                    total_indicated += 1
                    row.append(self._fmt(_("OK")))
                elif date_status == CALLBACK_MISSED:
                    total_indicated += 1
                    total_no_response += 1
                    row.append(self._fmt_highlight(_("No Response")))
                else:
                    row.append(self._fmt(_("not indicated")))
            
            if total_no_response > 0:
                row[1] = self._fmt_highlight(total_no_response)
            else:
                row[1] = self._fmt(total_no_response)
            row[2] = self._fmt(total_indicated)
            row[3] = self._fmt(total_pending)
            
            result.append(row)
        
        return result
    
    def _fmt(self, value):
        return self.table_cell(value, '<div style="text-align:center">%s</div>' % value)
    
    def _fmt_highlight(self, value):
        return self.table_cell(value, '<div style="background-color:#f33; font-weight:bold; text-align:center">%s</div>' % value)


CUSTOM_REPORTS = (
    ('Custom Reports', (
        MissedCallbackReport,
    )),
)

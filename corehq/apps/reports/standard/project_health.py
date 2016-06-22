from collections import namedtuple
import datetime
from django.utils.translation import ugettext_noop
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.domain.models import Domain
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.style.decorators import use_nvd3
from corehq.apps.users.util import raw_username
from corehq.toggles import PROJECT_HEALTH_DASHBOARD
from dimagi.ext import jsonobject
from dimagi.utils.dates import add_months
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.es.groups import GroupES
from corehq.apps.es.users import UserES
from itertools import chain
from corehq.apps.locations.models import SQLLocation


def get_performance_threshold(domain_name):
    return Domain.get_by_name(domain_name).internal.performance_threshold or 15


class UserActivityStub(namedtuple('UserStub', ['user_id', 'username', 'num_forms_submitted',
                                               'is_performing', 'previous_stub', 'next_stub'])):

    @property
    def is_active(self):
        return self.num_forms_submitted > 0

    @property
    def is_newly_performing(self):
        return self.is_performing and (self.previous_stub is None or not self.previous_stub.is_performing)

    @property
    def delta_forms(self):
        previous_forms = 0 if self.previous_stub is None else self.previous_stub.num_forms_submitted
        return self.num_forms_submitted - previous_forms

    @property
    def num_forms_submitted_next_month(self):
        return self.next_stub.num_forms_submitted if self.next_stub else 0

    @property
    def delta_forms_next_month(self):
        return self.num_forms_submitted_next_month - self.num_forms_submitted


class MonthlyPerformanceSummary(jsonobject.JsonObject):
    month = jsonobject.DateProperty()
    domain = jsonobject.StringProperty()
    performance_threshold = jsonobject.IntegerProperty()
    active = jsonobject.IntegerProperty()
    performing = jsonobject.IntegerProperty()

    def __init__(self, domain, month, users, has_filters, performance_threshold, previous_summary=None):
        self._previous_summary = previous_summary
        self._next_summary = None
        base_queryset = MALTRow.objects.filter(
            domain_name=domain,
            month=month,
            user_type__in=['CommCareUser', 'CommCareUser-Deleted'],
        )
        if has_filters:
            base_queryset = base_queryset.filter(
                user_id__in=users,
            )
        self._distinct_user_ids = base_queryset.distinct('user_id')

        num_performing_user = (base_queryset
                               .filter(num_of_forms__gte=performance_threshold)
                               .distinct('user_id')
                               .count())

        super(MonthlyPerformanceSummary, self).__init__(
            month=month,
            domain=domain,
            performance_threshold=performance_threshold,
            active=self._distinct_user_ids.count(),
            performing=num_performing_user,
        )

    def set_next_month_summary(self, next_month_summary):
        self._next_summary = next_month_summary

    @property
    def number_of_performing_users(self):
        return self.performing

    @property
    def number_of_active_users(self):
        return self.active

    @property
    def previous_month(self):
        prev_year, prev_month = add_months(self.month.year, self.month.month, -1)
        return datetime.datetime(prev_year, prev_month, 1)

    @property
    def delta_performing(self):
        if self._previous_summary:
            return self.number_of_performing_users - self._previous_summary.number_of_performing_users
        else:
            return self.number_of_performing_users

    @property
    def delta_performing_pct(self):
        if self.delta_performing and self._previous_summary and self._previous_summary.number_of_performing_users:
            return float(self.delta_performing / float(self._previous_summary.number_of_performing_users)) * 100.

    @property
    def delta_active(self):
        return self.active - self._previous_summary.active if self._previous_summary else self.active

    @property
    def delta_active_pct(self):
        if self.delta_active and self._previous_summary and self._previous_summary.active:
            return float(self.delta_active / float(self._previous_summary.active)) * 100.

    @memoized
    def get_all_user_stubs(self):
        return {
            row.user_id: UserActivityStub(
                user_id=row.user_id,
                username=raw_username(row.username),
                num_forms_submitted=row.num_of_forms,
                is_performing=row.num_of_forms >= self.performance_threshold,
                previous_stub=None,
                next_stub=None,
            ) for row in self._distinct_user_ids
        }

    @memoized
    def get_all_user_stubs_with_extra_data(self):
        if self._previous_summary:
            previous_stubs = self._previous_summary.get_all_user_stubs()
            next_stubs = self._next_summary.get_all_user_stubs() if self._next_summary else {}
            user_stubs = self.get_all_user_stubs()
            ret = []
            for user_stub in user_stubs.values():
                ret.append(UserActivityStub(
                    user_id=user_stub.user_id,
                    username=user_stub.username,
                    num_forms_submitted=user_stub.num_forms_submitted,
                    is_performing=user_stub.is_performing,
                    previous_stub=previous_stubs.get(user_stub.user_id),
                    next_stub=next_stubs.get(user_stub.user_id),
                ))
            for missing_user_id in set(previous_stubs.keys()) - set(user_stubs.keys()):
                previous_stub = previous_stubs[missing_user_id]
                ret.append(UserActivityStub(
                    user_id=previous_stub.user_id,
                    username=previous_stub.username,
                    num_forms_submitted=0,
                    is_performing=False,
                    previous_stub=previous_stub,
                    next_stub=next_stubs.get(missing_user_id),
                ))
            return ret

    def get_unhealthy_users(self):
        """
        Get a list of unhealthy users - defined as those who were "performing" last month
        but are not this month (though are still active).
        """
        if self._previous_summary:
            unhealthy_users = filter(
                lambda stub: stub.is_active and not stub.is_performing,
                self.get_all_user_stubs_with_extra_data()
            )
            return sorted(unhealthy_users, key=lambda stub: stub.delta_forms)

    def get_dropouts(self):
        """
        Get a list of dropout users - defined as those who were active last month
        but are not active this month
        """
        if self._previous_summary:
            dropouts = filter(
                lambda stub: not stub.is_active,
                self.get_all_user_stubs_with_extra_data()
            )
            return sorted(dropouts, key=lambda stub: stub.delta_forms)

    def get_newly_performing(self):
        """
        Get a list of "newly performing" users - defined as those who are "performing" this month
        after not performing last month.
        """
        if self._previous_summary:
            dropouts = filter(
                lambda stub: stub.is_newly_performing,
                self.get_all_user_stubs_with_extra_data()
            )
            return sorted(dropouts, key=lambda stub: -stub.delta_forms)


class ProjectHealthDashboard(ProjectReport):
    slug = 'project_health'
    name = ugettext_noop("Project Performance")
    base_template = "reports/project_health/project_health_dashboard.html"

    fields = [
        'corehq.apps.reports.filters.location.LocationGroupFilter',
    ]

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return PROJECT_HEALTH_DASHBOARD.enabled(domain)

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(ProjectHealthDashboard, self).decorator_dispatcher(request, *args, **kwargs)

    def get_group_location_ids(self):
        params = self.request.GET.getlist('grouplocationfilter')
        if params == [u'']:
            params = []
        return params

    def parse_param_to_loc_group(self, param_ids):
        locationids_param = []
        groupids_param = []

        if param_ids:
            param_ids = param_ids[0].split(',')
            for id in param_ids:
                if id.startswith("g__"):
                    groupids_param.append(id[3:])
                elif id.startswith("l__"):
                    loc = SQLLocation.by_location_id(id[3:])
                    if loc.get_descendants():
                        locationids_param.extend(loc.get_descendants().location_ids())
                    locationids_param.append(id[3:])

        return locationids_param, groupids_param

    def get_users_by_filter(self):
        locationids_param, groupids_param = self.parse_param_to_loc_group(self.get_group_location_ids())

        users_lists_by_location = (UserES()
                                   .domain(self.domain)
                                   .location(locationids_param)
                                   .values_list('_id', flat=True))
        users_list_by_group = (GroupES()
                               .domain(self.domain)
                               .group_ids(groupids_param)
                               .values_list("users", flat=True))
        if locationids_param and groupids_param:
            users_set = set(chain(*users_list_by_group)).union(users_lists_by_location)
        elif locationids_param:
                users_set = set(users_lists_by_location)
        else:
            users_set = set(chain(*users_list_by_group))
        return users_set

    def previous_six_months(self):
        now = datetime.datetime.utcnow()
        six_month_summary = []
        last_month_summary = None
        performance_threshold = get_performance_threshold(self.domain)
        filtered_users = self.get_users_by_filter()
        for i in range(-5, 1):
            year, month = add_months(now.year, now.month, i)
            month_as_date = datetime.date(year, month, 1)
            this_month_summary = MonthlyPerformanceSummary(
                domain=self.domain,
                performance_threshold=performance_threshold,
                month=month_as_date,
                previous_summary=last_month_summary,
                users=filtered_users,
                has_filters=bool(self.get_group_location_ids()),
            )
            six_month_summary.append(this_month_summary)
            if last_month_summary is not None:
                last_month_summary.set_next_month_summary(this_month_summary)
            last_month_summary = this_month_summary
        return six_month_summary

    @property
    def template_context(self):
        six_months_reports = self.previous_six_months()
        performance_threshold = get_performance_threshold(self.domain)
        return {
            'six_months_reports': six_months_reports,
            'this_month': six_months_reports[-1],
            'last_month': six_months_reports[-2],
            'threshold': performance_threshold,
        }

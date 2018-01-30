from __future__ import absolute_import
from itertools import groupby
from collections import defaultdict
from xml.etree.cElementTree import Element

from casexml.apps.phone.fixtures import FixtureProvider
from corehq.apps.custom_data_fields.dbaccessors import get_by_domain_and_type
from corehq.apps.fixtures.utils import get_index_schema_node
from corehq.apps.locations.cte import With
from corehq.apps.locations.models import SQLLocation, LocationType, LocationFixtureConfiguration
from corehq import toggles

import six
from django.db.models import Field, IntegerField, Lookup
from django.db.models.expressions import (
    Case, Exists, ExpressionWrapper, F, Func, OuterRef, RawSQL, Subquery,
    Value, When,
)
from django.db.models.query import Q
from django.db.models.aggregates import Max
from django.contrib.postgres.fields.array import ArrayField


class LocationSet(object):
    """
    Very simple class for keeping track of a set of locations
    """

    def __init__(self, locations=None):
        self.by_id = {}
        self.root_locations = set()
        self.by_parent = defaultdict(set)
        if locations is not None:
            for loc in locations:
                self.add_location(loc)

    def add_location(self, location):
        self.by_id[location.location_id] = location
        parent = location.parent
        parent_id = parent.location_id if parent else None
        if parent_id is None:  # this is a root
            self.add_root(location)
        self.by_parent[parent_id].add(location)

    def add_root(self, location):
        self.root_locations.add(location)

    def __contains__(self, item):
        return item in self.by_id


def should_sync_locations(last_sync, locations_queryset, restore_user):
    """
    Determine if any locations (already filtered to be relevant
    to this user) require syncing.
    """
    if (
        not last_sync or
        not last_sync.date or
        restore_user.get_fixture_last_modified() >= last_sync.date
    ):
        return True

    return (
        locations_queryset.filter(last_modified__gte=last_sync.date).exists()
        or LocationType.objects.filter(domain=restore_user.domain,
                                       last_modified__gte=last_sync.date).exists()
    )


class LocationFixtureProvider(FixtureProvider):

    def __init__(self, id, serializer):
        self.id = id
        self.serializer = serializer

    def __call__(self, restore_state):
        """
        By default this will generate a fixture for the users
        location and it's "footprint", meaning the path
        to a root location through parent hierarchies.

        There is an admin feature flag that will make this generate
        a fixture with ALL locations for the domain.
        """
        restore_user = restore_state.restore_user

        if not self.serializer.should_sync(restore_user):
            return []

        # This just calls get_location_fixture_queryset but is memoized to the user
        locations_queryset = restore_user.get_locations_to_sync()
        if not should_sync_locations(restore_state.last_sync_log, locations_queryset, restore_user):
            return []

        data_fields = _get_location_data_fields(restore_user.domain)
        return self.serializer.get_xml_nodes(self.id, restore_user, locations_queryset, data_fields)


class HierarchicalLocationSerializer(object):

    def should_sync(self, restore_user):
        return should_sync_hierarchical_fixture(restore_user.project)

    def get_xml_nodes(self, fixture_id, restore_user, locations_queryset, data_fields):
        locations_db = LocationSet(locations_queryset)

        root_node = Element('fixture', {'id': fixture_id, 'user_id': restore_user.user_id})
        root_locations = locations_db.root_locations

        if root_locations:
            _append_children(root_node, locations_db, root_locations, data_fields)
        else:
            # There is a bug on mobile versions prior to 2.27 where
            # a parsing error will cause mobile to ignore the element
            # after this one if this element is empty.
            # So we have to add a dummy empty_element child to prevent
            # this element from being empty.
            root_node.append(Element("empty_element"))
        return [root_node]


class FlatLocationSerializer(object):

    def should_sync(self, restore_user):
        return should_sync_flat_fixture(restore_user.project)

    def get_xml_nodes(self, fixture_id, restore_user, locations_queryset, data_fields):

        all_types = LocationType.objects.filter(domain=restore_user.domain).values_list(
            'code', flat=True
        )
        location_type_attrs = ['{}_id'.format(t) for t in all_types if t is not None]
        attrs_to_index = ['@{}'.format(attr) for attr in location_type_attrs]
        attrs_to_index.extend(_get_indexed_field_name(field.slug) for field in data_fields
                              if field.index_in_fixture)
        attrs_to_index.extend(['@id', '@type', 'name'])

        return [get_index_schema_node(fixture_id, attrs_to_index),
                self._get_fixture_node(fixture_id, restore_user, locations_queryset,
                                       location_type_attrs, data_fields)]

    def _get_fixture_node(self, fixture_id, restore_user, locations_queryset,
                          location_type_attrs, data_fields):
        root_node = Element('fixture', {'id': fixture_id,
                                        'user_id': restore_user.user_id,
                                        'indexed': 'true'})
        outer_node = Element('locations')
        root_node.append(outer_node)
        all_locations = list(locations_queryset.order_by('site_code'))
        locations_by_id = {location.pk: location for location in all_locations}
        for location in all_locations:
            attrs = {
                'type': location.location_type.code,
                'id': location.location_id,
            }
            attrs.update({attr: '' for attr in location_type_attrs})
            attrs['{}_id'.format(location.location_type.code)] = location.location_id

            current_location = location
            while current_location.parent_id:
                try:
                    current_location = locations_by_id[current_location.parent_id]
                except KeyError:
                    current_location = current_location.parent

                    # For some reason this wasn't included in the locations we already fetched
                    from corehq.util.soft_assert import soft_assert
                    _soft_assert = soft_assert('{}@{}.com'.format('frener', 'dimagi'))
                    message = (
                        "The flat location fixture didn't prefetch all parent "
                        "locations: {domain}: {location_id}. User id: {user_id}"
                    ).format(
                        domain=current_location.domain,
                        location_id=current_location.location_id,
                        user_id=restore_user.user_id,
                    )
                    _soft_assert(False, msg=message)

                attrs['{}_id'.format(current_location.location_type.code)] = current_location.location_id

            location_node = Element('location', attrs)
            _fill_in_location_element(location_node, location, data_fields)
            outer_node.append(location_node)

        return root_node


def should_sync_hierarchical_fixture(project):
    # Sync hierarchical fixture for domains with fixture toggle enabled for migration and
    # configuration set to use hierarchical fixture
    # Even if both fixtures are set up, this one takes priority for domains with toggle enabled
    return (
        project.uses_locations and
        toggles.HIERARCHICAL_LOCATION_FIXTURE.enabled(project.name) and
        LocationFixtureConfiguration.for_domain(project.name).sync_hierarchical_fixture
    )


def should_sync_flat_fixture(project):
    # Sync flat fixture for domains with conf for flat fixture enabled
    # This does not check for toggle for migration to allow domains those domains to migrate to flat fixture
    return (
        project.uses_locations and
        LocationFixtureConfiguration.for_domain(project.name).sync_flat_fixture
    )


location_fixture_generator = LocationFixtureProvider(
    id='commtrack:locations', serializer=HierarchicalLocationSerializer()
)
flat_location_fixture_generator = LocationFixtureProvider(
    id='locations', serializer=FlatLocationSerializer()
)


int_field = IntegerField()
int_array = ArrayField(int_field)


class Array(Func):
    function = "Array"
    template = '%(function)s[%(expressions)s]'
    output_field = int_array


class array_append(Func):
    function = "array_append"
    output_field = int_array


@Field.register_lookup
class EqualsAny(Lookup):
    # Can't use Func for ANY(...) because functions are wrapped in parens
    # resulting in SQL like `... = (ANY(...))` which is not valid.
    lookup_name = "eq_any"

    def as_postgresql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return '%s = ANY(%s)' % (lhs, rhs), params


class WrapSQL(RawSQL):
    """Wrap ORM-generated SQL expression(s) with raw SQL

    Desparate measures for desparate times. Any `{named_sub_expression}`
    slugs in the "wrapper" SQL string will be filled with the
    corresponding ORM SQL expression passed as a keyword argument.
    """

    def __init__(self, _sql, **expressions):
        self.sql = _sql
        output_field = expressions.pop("output_field", Field())
        self.expressions = expressions
        # purposely skip RawSQL.__init__ by calling its super
        super(RawSQL, self).__init__(output_field=output_field)

    def __repr__(self):
        return "{}({}, {})".format(
            self.__class__.__name__, self.sql, self.expressions)

    def as_sql(self, compiler, connection):
        expressions = {}
        params = []
        for key, expr in self.expressions.items():
            if hasattr(expr, "get_compiler"):
                comp = expr.get_compiler(connection=connection)
                expr_sql, expr_params = comp.as_sql()
            else:
                expr_sql, expr_params = expr.as_sql(compiler, connection)
            expressions[key] = expr_sql
            params.extend(expr_params)
        return self.sql.format(**expressions), params

    def get_group_by_cols(self):
        return [self]


def get_location_fixture_queryset(user):

    # There may be ambiguities in location type configurations that could
    # cause undefined outcomes:
    # - expand_from_root = TRUE seems to do the same thing as
    #   include_without_expanding IS NOT NULL (redundant config?).
    # - expand_from_root = TRUE with expand_from IS NOT NULL seems logically
    #   inconsistent. Suggest adding check constraint to prevent this state.
    # - include_without_expanding IS NOT NULL with expand_from IS NOT NULL
    #   seems logically inconsistent. Suggest adding check constraint.
    # - expand_from could point to a location that is not an ancester
    # - expand_to could point to a location that is not a descendant (maybe
    #   doesn't matter since it's only used to calculate a depth).
    # - two location types along the same path could both have expand_to set
    #   to different levels, making the expansion depth ambiguous if a user
    #   had both of those locations.
    # - ancestors could be excluded with improper include_only config.
    #   seems like we could achieve the same thing with expand_from/expand_to

    if toggles.SYNC_ALL_LOCATIONS.enabled(user.domain):
        return SQLLocation.active_objects.filter(domain=user.domain).prefetch_related('location_type')

    user_locations = user.get_sql_locations(user.domain).prefetch_related('location_type')

    expand_to = _get_expand_to_depths_cte(user_locations)
    expand_from = _get_expansion_details_cte(user.domain, user_locations, expand_to)
    fixture_ids = _get_fixture_ids_cte(user.domain, expand_from)

    result = fixture_ids.join(
        SQLLocation.objects.all()
        .with_cte(expand_to)
        .with_cte(expand_from)
        .with_cte(fixture_ids),
        id=fixture_ids.col.id
    ).annotate(
        path=fixture_ids.col.path,
        depth=fixture_ids.col.depth,
    ).order_by("path")

    print(result.query)
    return result


def _get_expand_to_depths_cte(user_locations):
    """Get a CTE with location type ids and corresponding expand to depths

    This traverses the location type hierarchy, which is assumed to
    mirror the location hierarchy but contain many less records. The
    traversal is over user locations' types and their ancestors, so
    should be reasonably fast.

    CTE columns:
    - expand_to_type: location type id, -1 if include_without_expanding
    - expand_to_depth: expansion depth
    """
    def expand_to_cte(cte):
        return LocationType.objects.filter(
            id__in=Subquery(
                user_locations.filter(
                    location_type__expand_to__isnull=False,
                ).values("location_type__expand_to"),
            ),
        ).values(
            "parent_type_id",
            expand_to_type=F("id"),
            depth=Value(0, output_field=int_field),
        ).union(
            # get depths of include_only location types
            LocationType.objects.filter(id__in=WrapSQL(
                """(
                SELECT to_locationtype_id
                FROM locations_locationtype_include_only
                WHERE from_locationtype_id IN ({user_types})
                )""",
                user_types=user_locations.values("location_type").query,
            )).values(
                "parent_type_id",
                expand_to_type=F("id"),
                depth=Value(0, output_field=int_field),
            ),
            all=True,
        ).union(
            # include_without_expanding
            LocationType.objects.filter(
                id__in=Subquery(
                    user_locations.filter(
                        location_type__include_without_expanding__isnull=False,
                    ).values("location_type__include_without_expanding"),
                ),
            ).values(
                "parent_type_id",
                expand_to_type=Value(-1, output_field=int_field),
                depth=Value(0, output_field=int_field),
            ),
            all=True,
        ).union(
            cte.join(
                LocationType.objects.all(),
                id=cte.col.parent_type_id,
            ).values(
                "parent_type_id",
                expand_to_type=cte.col.expand_to_type,
                depth=cte.col.depth + Value(1, output_field=int_field),
            ),
            all=True,
        )
    cte = With.recursive(expand_to_cte)
    return With(
        cte.queryset().with_cte(cte).filter(
            # exclude all but the root items
            parent_type_id__isnull=True,
        ).order_by().values(
            "expand_to_type",
            expand_to_depth=Max(cte.col.depth, output_field=int_field),
        ),
        "expand_to",
    )


def _get_expansion_details_cte(domain, user_locations, expand_to):
    """Get a CTE with expand from location ids and expansion depths

    The traversal is over user locations and their ancestors, so should
    be reasonably fast.

    CTE columns:
    - loc_id: location id, null for include_without_expanding
    - depth: expand to depth. Negative values in this column have
      special meanings. See output examples below.

     loc_id | depth
    --------|-------
     NULL   |  3     -- include all locations with depth <= 3
     1      | -1     -- include location 1 (but do not expand)
     10     |  4     -- include all descendents of location 10 to depth 4
     100    | -2     -- include all ancestors of location 100
    """
    def expand_from_cte(cte):
        return SQLLocation.active_objects.filter(
            domain__exact=domain,
            id__in=Subquery(user_locations.values("id")),
        ).annotate(
            is_include_only_type=Exists(
                LocationType.objects
                .filter(included_in=OuterRef("location_type"))
                .values(value=Value(1, output_field=int_field)),
            ),
        ).values(
            "parent_id",
            expand_from_type=Case(
                When(
                    # if expand_from is set and not the current location type
                    # it will be one of this location's ancestors
                    Q(
                        location_type___expand_from__isnull=False,
                        location_type___expand_from_root=Value(False),
                        location_type__include_without_expanding__isnull=True,
                    ) & ~Q(location_type___expand_from=F("location_type")),
                    then=F("location_type___expand_from"),
                ),
                # otherwise it will be null for this and all ancestors
                default=Value(None),
                output_field=int_field,
            ),
            loc_id=Case(
                When(
                    # include_without_expanding or expand_from_root -> no path
                    Q(location_type___expand_from_root=Value(True)) |
                    Q(location_type__include_without_expanding__isnull=False),
                    then=Value(None),
                ),
                # first path element
                default=F("id"),
                output_field=int_field,
            ),
            depth=Case(
                When(
                    # get include_without_expanding depth
                    location_type__include_without_expanding__isnull=False,
                    then=Subquery(
                        expand_to.queryset()
                        .filter(expand_to_type=-1)
                        .values("expand_to_depth")
                    ),
                ),
                When(
                    # Expand to deepest include_only location type. This
                    # method of inclusion will also include all
                    # ancestors of locations included via include_only.
                    is_include_only_type=True,
                    then=RawSQL("""(
                        SELECT Max(expand_to_depth)
                        FROM locations_locationtype_include_only inc
                            INNER JOIN expand_to ext
                                ON expand_to_type = to_locationtype_id
                        WHERE from_locationtype_id = locations_locationtype.id
                    )""", []),
                ),
                When(
                    # get expand_to depth
                    location_type__expand_to__isnull=False,
                    then=Subquery(
                        expand_to.queryset()
                        .filter(expand_to_type=OuterRef("location_type__expand_to"))
                        .values("expand_to_depth")
                    ),
                ),
                # unlimited expansion depth
                default=Value(-2),
                output_field=int_field,
            ),
        ).union(
            cte.join(
                SQLLocation.active_objects.all(),
                id=cte.col.parent_id,
            ).annotate(
                cte_loc_id=ExpressionWrapper(
                    cte.col.loc_id,
                    output_field=int_field,
                ),
                cte_expand_from_type=ExpressionWrapper(
                    cte.col.expand_from_type,
                    output_field=int_field,
                ),
            ).values(
                "parent_id",
                expand_from_type=Case(
                    When(
                        # set expand_from_type if it will apply to an ancestor
                        Q(
                            Q(cte_expand_from_type__isnull=False),
                            ~Q(cte_expand_from_type=F("location_type")),
                        ),
                        then=cte.col.expand_from_type,
                    ),
                    # otherwise it will be null for this and all ancestors
                    default=Value(None),
                    output_field=int_field,
                ),
                loc_id=Case(
                    # include_without_expanding or expand_from_root -> no path
                    When(cte_loc_id__isnull=True, then=Value(None)),
                    # next element of path
                    default=F("id"),
                    output_field=int_field,
                ),
                depth=Case(
                    When(
                        # ancestor of expand_from -> include but do not expand
                        cte_loc_id__isnull=False,
                        cte_expand_from_type__isnull=True,
                        then=Value(-1),
                    ),
                    # no path yet or starting path -> use previous depth
                    default=cte.col.depth,
                    output_field=int_field,
                ),
            ),
            all=True,
        )
    cte = With.recursive(expand_from_cte)
    return With(
        cte.queryset().with_cte(cte).order_by().values(
            "loc_id",
            "depth",
        ).distinct(),
        "expand_from",
    )


def _get_fixture_ids_cte(domain, expand_from):
    """Get fixture locations using expand_from criteria

    CTE columns:
    - id: location id
    - parent_id: location parent id
    - depth: depth in locations tree (0 is root node)
    - path: location tree path from root (array of location ids)
    """
    def is_included(depth_expr, path_expr):
        return Exists(
            expand_from.queryset().annotate(
                # HACK use RawSQL because OuterRef is broken
                # https://code.djangoproject.com/ticket/28621
                outer_id=RawSQL(
                    '"locations_sqllocation"."id"', [],
                    output_field=int_field,
                ),
            ).filter(Q(
                # ancestor of expand_from
                # or expansion depth is unlimited
                # or descendant of expand_from within expand_to depth
                Q(depth=-1) | Q(depth=-2) | Q(depth__gte=depth_expr),
                loc_id=F("outer_id"),
            ) | Q(
                # include_without_expanding/expand_from_root
                # unlimited depth or depth >= current depth
                Q(depth=-2) | Q(depth__gte=depth_expr),
                loc_id__isnull=True,
            ) | Q(
                # expansion depth is unlimited
                # or descendant of expand_from within expand_to depth
                Q(depth=-2) | Q(depth__gte=depth_expr),
                loc_id__eq_any=path_expr,
            )).values(value=Value(1, output_field=int_field)),
        )

    def fixture_ids_cte(cte):
        return SQLLocation.active_objects.annotate(
            is_included=is_included(Value(0), Array("outer_id")),
        ).values(
            "id",
            "parent_id",
            depth=Value(0, output_field=int_field),
            path=Array("id"),
        ).filter(
            domain__exact=domain,
            parent__isnull=True,  # start at the root
            is_included=True,
        ).union(
            cte.join(
                SQLLocation.active_objects.all(),
                parent_id=cte.col.id,
            ).annotate(
                depth=cte.col.depth + Value(1, output_field=int_field),
                path=array_append(cte.col.path, "id"),
                is_included=is_included(
                    cte.col.depth + Value(1, output_field=int_field),
                    array_append(cte.col.path, "outer_id"),
                ),
            ).filter(
                domain__exact=domain,
                is_included=True,
            ).values(
                "id",
                "parent_id",
                "depth",
                "path",
            ),
            all=True,
        )
    return With.recursive(fixture_ids_cte, "fixture_ids")


#def get_location_fixture_queryset(user):
#    if toggles.SYNC_ALL_LOCATIONS.enabled(user.domain):
#        return SQLLocation.active_objects.filter(domain=user.domain).prefetch_related('location_type')
#
#    user_locations = user.get_sql_locations(user.domain).prefetch_related('location_type')
#
#    all_locations = _get_include_without_expanding_locations(user.domain, user_locations)
#
#    for user_location in user_locations:
#        location_type = user_location.location_type
#        # returns either None or the level (integer) to exand to
#        expand_to_level = _get_level_to_expand_to(user.domain, location_type.expand_to)
#        expand_from_level = location_type.expand_from or location_type
#
#        # returns either all root locations or a single location (of expand_from_level type)
#        expand_from_locations = _get_locs_to_expand_from(user.domain, user_location, expand_from_level)
#
#        locs_below_expand_from = _get_children(expand_from_locations, expand_to_level)
#        locs_at_or_above_expand_from = (SQLLocation.active_objects
#                                        .get_queryset_ancestors(expand_from_locations, include_self=True))
#        locations_to_sync = locs_at_or_above_expand_from | locs_below_expand_from
#        if location_type.include_only.exists():
#            locations_to_sync = locations_to_sync.filter(location_type__in=location_type.include_only.all())
#        all_locations |= locations_to_sync
#
#    return all_locations


def _get_level_to_expand_to(domain, expand_to):
    if expand_to is None:
        return None
    return (SQLLocation.active_objects
            .filter(domain__exact=domain, location_type=expand_to)
            .values_list('level', flat=True)
            .first())


def _get_locs_to_expand_from(domain, user_location, expand_from):
    """From the users current location, return all locations of the highest
    level they want to start expanding from.
    """
    if user_location.location_type.expand_from_root:
        return SQLLocation.root_locations(domain=domain)
    else:
        ancestors = (
            user_location
            .get_ancestors(include_self=True)
            .filter(location_type=expand_from, is_archived=False)
            .prefetch_related('location_type')
        )
        return ancestors


def _get_children(expand_from_locations, expand_to_level):
    """From the topmost location, get all the children we want to sync
    """
    children = (SQLLocation.active_objects
                .get_queryset_descendants(expand_from_locations)
                .prefetch_related('location_type'))
    if expand_to_level is not None:
        children = children.filter(level__lte=expand_to_level)
    return children


def _get_include_without_expanding_locations(domain, assigned_locations):
    """returns all locations set for inclusion along with their ancestors
    """
    # all loctypes to include, based on all assigned location types
    location_type_ids = {
        loc.location_type.include_without_expanding_id
        for loc in assigned_locations
        if loc.location_type.include_without_expanding_id is not None
    }
    # all levels to include, based on the above loctypes
    forced_levels = (SQLLocation.active_objects
                     .filter(domain__exact=domain,
                             location_type_id__in=location_type_ids)
                     .values_list('level', flat=True)
                     .order_by('level')
                     .distinct('level'))
    if forced_levels:
        return (SQLLocation.active_objects
                .filter(domain__exact=domain,
                        level__lte=max(forced_levels))
                .prefetch_related('location_type'))
    else:
        return SQLLocation.objects.none()


def _append_children(node, location_db, locations, data_fields):
    for type, locs in _group_by_type(locations):
        locs = sorted(locs, key=lambda loc: loc.name)
        node.append(_types_to_fixture(location_db, type, locs, data_fields))


def _group_by_type(locations):
    key = lambda loc: (loc.location_type.code, loc.location_type)
    for (code, type), locs in groupby(sorted(locations, key=key), key=key):
        yield type, list(locs)


def _types_to_fixture(location_db, type, locs, data_fields):
    type_node = Element('%ss' % type.code)  # hacky pluralization
    for loc in locs:
        type_node.append(_location_to_fixture(location_db, loc, type, data_fields))
    return type_node


def _get_metadata_node(location, data_fields):
    node = Element('location_data')
    # add default empty nodes for all known fields: http://manage.dimagi.com/default.asp?247786
    for field in data_fields:
        element = Element(field.slug)
        element.text = six.text_type(location.metadata.get(field.slug, ''))
        node.append(element)
    return node


def _location_to_fixture(location_db, location, type, data_fields):
    root = Element(type.code, {'id': location.location_id})
    _fill_in_location_element(root, location, data_fields)
    _append_children(root, location_db, location_db.by_parent[location.location_id], data_fields)
    return root


def _fill_in_location_element(xml_root, location, data_fields):
    fixture_fields = [
        'name',
        'site_code',
        'external_id',
        'latitude',
        'longitude',
        'location_type',
        'supply_point_id',
    ]
    for field in fixture_fields:
        field_node = Element(field)
        val = getattr(location, field)
        field_node.text = six.text_type(val if val is not None else '')
        xml_root.append(field_node)

    # in order to be indexed, custom data fields need to be top-level
    # so we stick them in there with the prefix data_
    for field in data_fields:
        if field.index_in_fixture:
            field_node = Element(_get_indexed_field_name(field.slug))
            val = location.metadata.get(field.slug)
            field_node.text = six.text_type(val if val is not None else '')
            xml_root.append(field_node)

    xml_root.append(_get_metadata_node(location, data_fields))


def _get_location_data_fields(domain):
    from corehq.apps.locations.views import LocationFieldsView
    fields_definition = get_by_domain_and_type(domain, LocationFieldsView.field_type)
    if fields_definition:
        return fields_definition.fields
    else:
        return []


def _get_indexed_field_name(slug):
    return "data_{}".format(slug)

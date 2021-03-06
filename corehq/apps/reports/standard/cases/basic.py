import logging
from couchdbkit import RequestFailed
from django.utils.translation import ugettext_noop, ugettext
from django.utils.translation import ugettext as _
import simplejson
from corehq.apps.api.es import CaseES
from corehq.apps.groups.models import Group
from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.fields import SelectMobileWorkerField, SelectOpenCloseField
from corehq.apps.reports.filters.search import SearchFilter
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard import ProjectReportParametersMixin
from corehq.apps.reports.standard.cases.data_sources import CaseInfo, CaseDisplay
from corehq.apps.reports.standard.inspect import ProjectInspectionReport
from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators.memoized import memoized


class CaseListMixin(ElasticProjectInspectionReport, ProjectReportParametersMixin):
    fields = [
        'corehq.apps.reports.fields.FilterUsersField',
        'corehq.apps.reports.fields.SelectCaseOwnerField',
        'corehq.apps.reports.fields.CaseTypeField',
        'corehq.apps.reports.fields.SelectOpenCloseField',
        'corehq.apps.reports.standard.cases.filters.CaseSearchFilter',
    ]

    case_filter = {}
    ajax_pagination = True
    asynchronous = True

    @property
    @memoized
    def case_es(self):
        return CaseES(self.domain)


    def build_query(self, case_type=None, filter=None, status=None, owner_ids=None, search_string=None):
        # there's no point doing filters that are like owner_id:(x1 OR x2 OR ... OR x612)
        # so past a certain number just exclude
        owner_ids = owner_ids or []
        MAX_IDS = 50

        def _filter_gen(key, flist):
            if flist and len(flist) < MAX_IDS:
                yield {"terms": {
                    key: [item.lower() if item else "" for item in flist]
                }}

            # demo user hack
            elif flist and "demo_user" not in flist:
                yield {"not": {"term": {key: "demo_user"}}}

        def _domain_term():
            return {"term": {"domain.exact": self.domain}}

        subterms = [_domain_term(), filter] if filter else [_domain_term()]
        if case_type:
            subterms.append({"term": {"type.exact": case_type}})

        if status:
            subterms.append({"term": {"closed": (status == 'closed')}})

        user_filters = list(_filter_gen('owner_id', owner_ids))
        if user_filters:
            subterms.append({'or': user_filters})

        if search_string:
            query_block = {
                "query_string": {"query": search_string}}  # todo, make sure this doesn't suck
        else:
            query_block = {"match_all": {}}

        and_block = {'and': subterms} if subterms else {}

        es_query = {
            'query': {
                'filtered': {
                    'query': query_block,
                    'filter': and_block
                }
            },
            'sort': self.get_sorting_block(),
            'from': self.pagination.start,
            'size': self.pagination.count,
        }

        return es_query

    @property
    @memoized
    def es_results(self):
        case_es = self.case_es
        query = self.build_query(case_type=self.case_type, filter=self.case_filter,
                                 status=self.case_status, owner_ids=self.case_owners,
                                 search_string=SearchFilter.get_value(self.request, self.domain))
        query_results = case_es.run_query(query)

        if query_results is None or 'hits' not in query_results:
            logging.error("CaseListMixin query error: %s, urlpath: %s, params: %s, user: %s yielded a result indicating a query error: %s, results: %s" % (
                self.__class__.__name__,
                self.request.path,
                self.request.GET.urlencode(),
                self.request.couch_user.username,
                simplejson.dumps(query),
                simplejson.dumps(query_results)
            ))
            raise RequestFailed
        return query_results

    @property
    @memoized
    def case_owners(self):
        if self.individual:
            group_owners_raw = self.case_sharing_groups
        else:
            group_owners_raw = Group.get_case_sharing_groups(self.domain)
        group_owners = [group._id for group in group_owners_raw]
        ret = [user.get('user_id') for user in self.users]
        if len(self.request.GET.getlist('ufilter')) == 1 and str(HQUserType.UNKNOWN) in self.request.GET.getlist('ufilter'):
            #not applying group filter
            pass
        else:
            ret += group_owners
        return ret

    @property
    @memoized
    def case_sharing_groups(self):
        try:
            user = CommCareUser.get_by_user_id(self.individual)
            user = user if user.username_in_report else None
            return user.get_case_sharing_groups()
        except Exception:
            try:
                group = Group.get(self.individual)
                assert(group.doc_type == 'Group')
                return [group]
            except Exception:
                return []

    def get_case(self, row):
        if '_source' in row:
            case_dict = row['_source']
        else:
            raise ValueError("Case object is not in search result %s" % row)

        if case_dict['domain'] != self.domain:
            raise Exception("case.domain != self.domain; %r and %r, respectively" % (case_dict['domain'], self.domain))

        return case_dict

    @property
    def shared_pagination_GET_params(self):
        shared_params = super(CaseListMixin, self).shared_pagination_GET_params
        shared_params.append(dict(
            name=SelectOpenCloseField.slug,
            value=self.request.GET.get(SelectOpenCloseField.slug, '')
        ))
        return shared_params


class CaseListReport(CaseListMixin, ProjectInspectionReport, ReportDataSource):

    # note that this class is not true to the spirit of ReportDataSource; the whole
    # point is the decouple generating the raw report data from the report view/django
    # request. but currently these are too tightly bound to decouple

    name = ugettext_noop('Case List')
    slug = 'case_list'

    @property
    def user_filter(self):
        return super(CaseListReport, self).user_filter

    @property
    @memoized
    def rendered_report_title(self):
        if not self.individual:
            self.name = _("%(report_name)s for %(worker_type)s") % {
                "report_name": _(self.name),
                "worker_type": _(SelectMobileWorkerField.get_default_text(self.user_filter))
            }
        return self.name

    def slugs(self):
        return [
            '_case',
            'case_id',
            'case_name',
            'case_type',
            'detail_url',
            'is_open',
            'opened_on',
            'modified_on',
            'closed_on',
            'creator_id',
            'creator_name',
            'owner_type',
            'owner_id',
            'owner_name',
            'external_id',
        ]

    def get_data(self, slugs=None):
        for row in self.es_results['hits'].get('hits', []):
            case = self.get_case(row)
            ci = CaseInfo(self, case)
            data = {
                '_case': case,
                'detail_url': ci.case_detail_url,
            }
            data.update((prop, getattr(ci, prop)) for prop in (
                    'case_type', 'case_name', 'case_id', 'external_id',
                    'is_closed', 'opened_on', 'modified_on', 'closed_on',
                ))

            creator = ci.creating_user or {}
            data.update({
                'creator_id': creator.get('id'),
                'creator_name': creator.get('name'),
            })
            owner = ci.owner
            data.update({
                'owner_type': owner[0],
                'owner_id': owner[1]['id'],
                'owner_name': owner[1]['name'],
            })

            yield data

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Case Type"), prop_name="type.exact"),
            DataTablesColumn(_("Name"), prop_name="name.exact"),
            DataTablesColumn(_("Owner"), prop_name="owner_display", sortable=False),
            DataTablesColumn(_("Created Date"), prop_name="opened_on"),
            DataTablesColumn(_("Created By"), prop_name="opened_by_display", sortable=False),
            DataTablesColumn(_("Modified Date"), prop_name="modified_on"),
            DataTablesColumn(_("Status"), prop_name="get_status_display", sortable=False)
        )
        headers.custom_sort = [[5, 'desc']]
        return headers

    @property
    def rows(self):
        for data in self.get_data():
            display = CaseDisplay(self, data['_case'])

            yield [
                display.case_type,
                display.case_link,
                display.owner_display,
                display.opened_on,
                display.creating_user,
                display.modified_on,
                display.closed_display
            ]

    def date_to_json(self, date):
        if date:
            return date.strftime('%Y-%m-%d %H:%M:%S')
            # temporary band aid solution for http://manage.dimagi.com/default.asp?80262
            # return tz_utils.adjust_datetime_to_timezone(
            #     date, pytz.utc.zone, self.timezone.zone
            # ).strftime('%Y-%m-%d %H:%M:%S')
        else:
            return ''
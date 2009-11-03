#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.template.loader import render_to_string

import settings

from xformmanager.models import Metadata, FormDefModel, ElementDefModel
from reports.models import Case, SqlReport
from reports.util import get_whereclause
from shared import monitoring_report


'''Report file for custom Grameen reports'''
# see mvp.py for an explanation of how these are used.

# temporarily "privatizing" the name because grameen doesn't
# want this report to show up in the UI 
def _monitoring(request):
    '''Safe Pregnancy Monitoring Report'''
    safe_preg_case_name = "Grameen Safe Pregnancies"
    try:
        case = Case.objects.get(name=safe_preg_case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    
    return monitoring_report(request, case)
    
def chw_submission_details(request):
    '''Health Worker Submission Details'''
    # had to move this form a sql report to get in the custom annotations
    # this is a pretty ugly/hacky hybrid approach, and should certainly
    # be cleaned up
    extuser = request.extuser
    # hard coded to our fixture.  bad bad!
    grameen_submission_details_id = 2
    # hard coded to our schema.  bad bad!
    form_def = ElementDefModel.objects.get(table_name="schema_intel_grameen_safe_motherhood_registration_v0_3").form
    report = SqlReport.objects.get(id=grameen_submission_details_id)
    whereclause = get_whereclause(request.GET)  
    cols, data = report.get_data(whereclause)
    new_data = []
    for row in data:
        new_row_data = dict(zip(cols, row))
        row_id = new_row_data["row_id"]
        meta = Metadata.objects.get(formdefmodel=form_def, raw_data=row_id)
        new_row_data["Follow up?"] = meta.attachment.annotations.count() > 0
        new_row_data["meta"] = meta
        new_row_data["attachment"] = meta.attachment
        new_data.append(new_row_data)
    cols = cols[:6]
    return render_to_string("custom/grameen/chw_submission_details.html", 
                            {"MEDIA_URL": settings.MEDIA_URL, # we pretty sneakly have to explicitly pass this
                             "columns": cols,
                             "data": new_data})
    

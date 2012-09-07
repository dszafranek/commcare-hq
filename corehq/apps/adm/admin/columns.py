from corehq.apps.adm.admin import ADMAdminInterface
from corehq.apps.adm.forms import UpdateADMColumnForm, UpdateReducedADMColumnForm, DaysSinceADMColumnForm
from corehq.apps.adm.models import ReducedADMColumn, DaysSinceADMColumn, ConfigurableADMColumn
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from dimagi.utils.couch.database import get_db

class ADMColumnEditIterface(ADMAdminInterface):
    adm_item_type = "ADM Column"
    form_class = UpdateADMColumnForm

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Column Name"),
            DataTablesColumn("Description"),
            DataTablesColumn("Couch View"),
            DataTablesColumn("Key Format"),
            DataTablesColumn("Edit"),
        )

    @property
    def rows(self):
        rows = []
        key = ["all", self.property_class.__name__]
        data = self.property_class.view('adm/all_default_columns',
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key+[{}]
        ).all()
        for item in data:
            rows.append(item.as_row)
        return rows


class ReducedADMColumnInterface(ADMColumnEditIterface):
    name = "Reduced & Unfiltered ADM Columns"
    description = "Typically used for ADM Columns displaying a count (No. Cases or No. Submissions)."
    slug = "reduced_column"
    property_class = ReducedADMColumn
    form_class = UpdateReducedADMColumnForm

    adm_item_type = "Reduced ADM Column"
    detailed_description = """<p>This column returns the reduced value of the couch_view specified. This assumes that
    the reduced view returns a numerical value.</p>
    <p><strong>Example Usage:</strong> Columns that display a count, like # Cases or # Submissions.</p>"""

    @property
    def headers(self):
        header = super(ReducedADMColumnInterface, self).headers
        header.insert_column(DataTablesColumn("Returns a Number"), -1)
        header.insert_column(DataTablesColumn("Dates Span Duration of Project"), -1)
        return header


class DaysSinceADMColumnInterface(ADMColumnEditIterface):
    name = "Days Since ADM Column"
    description = "Columns that return the number of days since the specified datetime property occurred."
    slug = "days_since_column"
    property_class = DaysSinceADMColumn
    form_class = DaysSinceADMColumnForm

    adm_item_type = "Days Since ADM Column"
    detailed_description = """<p>Returns the number of days between the date of
    <span class="label">property_name</span> of the first item in the view and the
    startdate or enddate of the datespan.</p>"""

    @property
    def headers(self):
        header = super(DaysSinceADMColumnInterface, self).headers
        header.insert_column(DataTablesColumn("Property Name"), -1)
        header.insert_column(DataTablesColumn("Returns No. Days Between"), -1)
        return header


class ConfigurableADMColumnInterface(ADMColumnEditIterface):
    name = "User-Configurable ADM Columns"
    description = "Default definitions for user-configurable ADM Columns"
    slug = "config_column"
    property_class = ConfigurableADMColumn

    adm_item_type = "User-Configurable ADM Column"

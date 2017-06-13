from collections import namedtuple
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.app_manager.models import Module

class Lab(object):
    def __init__(self, slug, name, description, used_in_module=None, used_in_form=None):
        self.slug = slug
        self.name = name
        self.description = description

        self.used_in_module = used_in_module if used_in_module else lambda m: False
        self.used_in_form = used_in_form if used_in_form else lambda f: False

DISPLAY_CONDITIONS = Lab(
    slug="display_conditions",
    name="Form and Menu Display Conditions",
    description="TODO",
    used_in_form=lambda f: bool(f.form_filter),
    used_in_module=lambda m: bool(m.module_filter),
)

CASE_LIST_MENU_ITEM = Lab(
    slug="case_list_menu_item",
    name="Case List Menu Item",
    description="TODO",
    used_in_module=lambda m: isinstance(m, Module) and (m.case_list.show or m.task_list.show),  # TODO: will this break anything?
)

CASE_DETAIL_OVERWRITE = Lab(
    slug="case_detail_overwrite",
    name="Case Detail Overwrite",
    description="Ability to overwrite one case list or detail's settings with another's",
)

CONDITIONAL_FORM_ACTIONS = Lab(
    slug="conditional_form_actions",
    name='Allow opening or closing bases based on a condition ("Only if the answer to...")',
    description="Allow changing form actions, deleting registration forms (TODO: rephrase?)",
    used_in_form=lambda f: f.actions.open_case.condition.type === 'if' or f.actions.close_case.condition.type, # TODO: will this break advanced forms?
)

EDIT_FORM_ACTIONS = Lab(
    slug="edit_form_actions",
    name="Editing Form Actions",
    description="Allow changing form actions and deleting registration forms",
)

MENU_MODE = Lab(
    slug="menu_mode",
    name="Menu Mode",
    description="TODO",
    used_in_module=lambda m: return m.put_in_root,
)

REGISTER_FROM_CASE_LIST = Lab(
    slug="register_from_case_list",
    name="Register from case list",
    description="TODO",
    used_in_module=lambda m: module.case_list_form.form_id, # TODO: break anything
)

SUBCASES = Lab(
    slug="subcases",
    name="Child Cases",
    description="TODO",
    used_in_form=lambda f: bool(f.actions.subcases),    # TODO: will this break anything?
)

@memoized
def labs_by_name(app, slug):
    return {t['slug']: t for t in all_labs(app)}

@memoized
def all_labs(app, module=None, form=None):
    results = {}
    for name, lab in globals().items():
        if not name.startswith('__'):
            if isinstance(lab, Lab):
                show = enabled = lab.slug in app.labs and app.labs[lab.slug]
                if form:
                    show = show or lab.used_in_form(form)
                elif module:
                    show = show or lab.used_in_module(module)
                results[lab.slug] = {
                    'slug': lab.slug,
                    'name': lab.name,
                    'description': lab.description,
                    'enabled': enabled,
                    'show': show,
                }
    return results




'''
FEATURE PREVIEWS
Conditional Enum in Case List
Custom Calculations in Case List
Custom Single and Multiple Answer Questions
Icons in Case List
'''

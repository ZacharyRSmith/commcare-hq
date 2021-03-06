# Analytics
We use multiple analytics platforms, tracking events used primarily by the product and growth teams. This includes tracking general usage (like page visits), tracking custom events (like when a user clicks a specific button), and managing A/B tests.

[Directory of events and properties we track in these platforms](https://docs.google.com/spreadsheets/d/1frMdFeznNcMAIyMW3pG3zes6mmY03UG67HyMUHXlb-s/edit#gid=1804103672)

## Technical Overview

### Server Side

This varies depending on the service; see details on individual services below.

### Client Side

For passing data from the server to the client, which is mostly API keys, analytics uses a variation on [initial_page_data](https://github.com/dimagi/js-guide/blob/master/integration-patterns.md): same general idea, but with better namespacing and accessed via [initial.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/static/analytix/js/initial.js). Most of the analytics templates just contain this initial data, while a few contain the actual third-party scripts (for the services that don't interact with any other HQ JavaScript).

Analytics has its own logging infrastructure, is set up in [logging.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/static/analytix/js/logging.js) and prints to the browser console. The logging level can be controlled via `settings.ANALYTICS_CONFIG['LOG_LEVEL']` (see "Debugging" below).

Analytics code is inherently somewhat fragile because it depends on third-party services. There are two ways this fragility has repeatedly manifested:
- Script inclusions: Each service has a script they host that we have to include on our pages, which may fail due to an adblocker or other reason. Analytics needs to fail gracefully in these cases. This leads to analytics code being promise-driven.
- Callbacks: Events are often fired when a user takes an action that will lead them to a different page. The event triggers an ajax request to the third-party service, and we have to wait for it to complete before letting the user move on, since leaving the page would cancel the pending request and we'd lose the data. This leads to a pattern where the "main" behavior of a tracked button (e.g., submitting a form) is contained in a callback which is executed when the analytics request is finished (or when that request has failed, or when that request has taken too long to justify making the user wait for it...).

Beyond the general infrastructure, there's a JavaScript module for each of the major analytics services. Each of these has initialization logic that checks if analytics is available for the given server and user, loads the service's script(s), and then typically makes a call to the service to identify the current user. These modules generally expose one or more tracking functions to be called from various other parts of HQ.

### A/B tests

New tests need to be added to [ab_tests](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/ab_tests.py). Typically, view code will check the test's `version` and set a corresponding flag in the template context, which will then use that flag to deliver the appropriate content for the user's test group.

### Debugging

Useful localsettings when working with analytics:
- `ANALYTICS_IDS`: Analytics code doesn't run if the relevant API key isn't provided. For most purposes, setting the key to a dummy value is sufficient. We have test API keys for Google Analytics and Kissmetrics; you can pull these from the [staging vault](https://github.com/dimagi/commcare-cloud/tree/master/ansible#managing-secrets-with-vault).
- `ANALYTICS_CONFIG.DEBUG`: Analytics code isn't run on every server. Set `DEBUG` to `True` to bypass these checks (you still need to set the API keys, too).
- `ANALYTICS_CONFIG.LOG_LEVEL`: Controls the client-side logging. Turning it up to `verbose` can help debug.

## Individual Services

### Google Analytics

Used primarily by product team.

No server component, just [google.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/static/analytix/js/google.js). We track events using `<module>.track.click` and `<module>.track.event`. We also use the default tracking (page views, etc.). Google has a few tracking options; we use their [gtag.js](https://developers.google.com/analytics/devguides/collection/gtagjs/).

### Kissmetrics

Used primarily by product team.

Most A/B tests are tracked using client side Kissmetrics code, so [kissmetrix.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/static/analytix/js/kissmetrix.js) includes test setup.

Most events are tracked client side using `<module>.track.event`. Some are done server side, using `track_workflow` and `identify` functions in the [analytics tasks](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/tasks.py) file. `track_workflow` is used to register events and accepts an optional argument to update properties as well. `identify` can be used if you are only looking to update a property. From the data side, it doesn't matter whether the tracking was done on the client or the server.

In addition to the event-based code, the `track_periodic_data` task runs nightly and sends a variety of aggregated data to Hubspot and Kissmetrics (form submission count, mobile worker count, etc.).

### HubSpot

Used heavily by growth team.

Most of the code is server side [analytics tasks](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/tasks.py) that sends a "form" to Hubspot when a particular action happens on HQ.

On the client side, [hubspot.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/static/analytix/js/hubspot.js) has functions to identify users and track events, but these are barely used. We do include a Hubspot-provided script that tracks basic usage (e.g., page visits) and also sets a cookie to identify the user (described [here](https://knowledge.hubspot.com/articles/kcs_article/reports/what-cookies-does-hubspot-set-in-a-visitor-s-browser) as the "hubspotutk" cookie). The server's form-sending code checks for this cookie and, if it isn't present, doesn't send forms.

In addition to the event-based code, the `track_periodic_data` task runs nightly and sends a variety of aggregated data to Hubspot and Kissmetrics (form submission count, mobile worker count, etc.).

#### Adding/Removing Hubspot properties

We track various user properties as [Hubspot Contact Properties](http://knowledge.hubspot.com/contacts-user-guide-v2/how-to-use-contact-and-company-properties). We have bunch of celery tasks and function that update these contact properties via [Hubspot REST API](http://developers.hubspot.com/docs/methods/contacts/create_or_update). We can update only those properties that are available on Hubspot portal. When we mention new Hubspot properties in HQ-Hubspot API calls, make sure that these properties are available in Hubspot portal. If they are not available, [create](http://knowledge.hubspot.com/contacts-user-guide-v2/how-to-create-contact-and-company-properties) them or ping marketing team to have them created on Hubspot portal first. To update a list of properties you can use the [update_hubspot_properties](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/tasks.py#L174) function.

#### Hubspot Form Submissions
We use the hubspot form API to submit forms to hubspot via the `_send_form_to_hubspot` function in the analytics tasks file. You can look through that file for examples but the general procedure is to create a new function with the `@analytics_task()` decorator to make it asynchronous and ensure it is retried on failure. This function should then call `_send_form_to_hubspot` with the form id of the form you are trying to submit. All form ids are listed as constants at the top of the file, and new forms can be created on the hubspot site.

#### Signup Related Hubspot Analytics
Much of the analytics we use in hubspot are generated during the signup process. We send down those analytics in the `track_user_sign_in_on_hubspot` [function](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/tasks.py#L181). Both a dictionary or properties, and a special signup form are sent down then and if changes need to be made to sign up analytics, they should be made there.

#### Testing

To start testing, run Celery and update `HUBSPOT_API_KEY` and `HUBSPOT_ID` in `settings.ANALYTICS_IDS`. Hubspot provides a public demo portal with API access for testing. The credentials for this are available on their [API overview page](http://developers.hubspot.com/docs/overview). If you need to test using our production portal the credentials can be found in dimagi_shared keepass. Let marketing know before testing on production portal and clean up after the testing is finished

When troubleshooting in Hubspot's portal, it's often useful to create lists based on key events.

### Drift

This is the live chat feature available primarily on prelogin and for new users. There's a [drift.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/static/analytix/js/drift.js) HQ module, though it doesn't do much. No server component.

### Fullstory

Generally available in areas of interest to the product and growth teams: prelogin, signup, app builder, report builder. We include their script but there's no other interaction with their code - no events, etc. Not much related code; there's a [fullstory.html](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/templates/analytics/fullstory.html) template to include their script but no HQ JavaScript module and no server component.

### Facebook Pixel

Their script is included in [signup](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/registration/templates/registration/register_new_user.html), but we don't do any event tracking or other interaction with it. Very little related code, just the script inclusion.

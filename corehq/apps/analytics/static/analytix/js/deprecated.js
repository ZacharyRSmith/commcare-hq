/* globals _, _kmq */

// Deprecated analytics globals
var ga_track_event, // eslint-disable-line no-unused-vars
    trackLinkHelper, // eslint-disable-line no-unused-vars
    gaTrackLink, // eslint-disable-line no-unused-vars
    kmqPushSafe, // eslint-disable-line no-unused-vars
    analytics; // eslint-disable-line no-unused-vars

window.analytics = {};

// to support deprecated direct ga() calls
var ga = window.ga || function () {
    var _global = hqImport('analytics/js/initial').getFn('global');
    if (_global('isEnabled')) {
        hqImport('analytics/js/google').logger.warning.log(arguments, 'no global ga function was defined');
        if (arguments.length) {
            var lastArg = arguments[arguments.length - 1];
            if (lastArg) {
                var callback = lastArg.hitCallback;
                if (callback) {
                    callback();
                }
            }
        }
    }
};

/**
 * This creates wrappers with warnings around legacy global functions to help with refactoring of HQ's analytics.
 * Eventually this will be phased out and all the old globals replaced.
 */
hqDefine('analytics/js/deprecated', function () {
    'use strict';
    var _utils = hqImport('analytics/js/utils'),
        _kissmetrics = hqImport('analytics/js/kissmetrics'),
        _google = hqImport('analytics/js/google'),
        _global = hqImport('analytics/js/initial').getFn('global');

    /**
     * Helper function for wrapping the legacy functions.
     * @param {object} api - the analytics api
     * @param {string} fnName - Deprecated Function Name
     * @param {function} fallbackFn - Function to fallback to.
     * @param {function} formatArgs - (optional) Function that takes an array of arguments and reformats the arguments for fallback function.
     * @returns {Function} A function that takes the same paramers as the legacy function, but processes it in the new world and warns of its usage.
     * @private
     */
    var _makeLegacyFn = function(api, fnName, fallbackFn, formatArgs) {
        return function () {
            var args = Array.from(arguments);
            api.logger.deprecated.log(arguments, fnName);
            if (_.isFunction(formatArgs)) {
                args = formatArgs(args);
            }
            return fallbackFn.apply(null, args);
        };
    };

    /**
     * Gets the callback frunction (from Google Analytics' hitCallback) from the last argument, if available,
     * and re-adds to arguments
     * @param args - Array of arguments
     * @returns {array} - Array of arguments
     * @private
     */
    var _addCallbackToArgs = function (args) {
        var lastArg = _.last(args);
        if (lastArg && _.isFunction(lastArg.hitCallback)) {
            delete lastArg.hitCallback;
            args = _.union(args, [lastArg.hitCallback]);
        }
        return args;
    };
    if (_global('isEnabled')) {
        ga_track_event = _makeLegacyFn(_google, 'ga_track_event', _google.track.event, _addCallbackToArgs); // eslint-disable-line no-global-assign

        // Debug gtag's use of the ga function vs. the old usages
        var _oldGA = ga;
        ga = function () {
            var args = Array.from(arguments);
            if (args.length > 1 && args[0].startsWith('gtag')) {
                _google.logger.debug.log(arguments, 'direct gtag > ga call');
            } else if (args.length > 2 && args[1] === 'event') {
                args = args.splice(2);
                args = _addCallbackToArgs(args);
                _google.logger.deprecated.log(arguments, 'ga');
                return _google.track.event.apply(null, args);
            } else {
                _google.logger.debug.log(arguments, 'unknown ga call');
            }
            return _oldGA.apply(null, arguments);
        };
        trackLinkHelper = _makeLegacyFn(_google, 'trackLinkHelper', _utils.trackClickHelper);
        gaTrackLink = _makeLegacyFn(_google, 'gaTrackLink', _google.track.click);
        kmqPushSafe = _makeLegacyFn(_kissmetrics, 'kmqPushSafe', function (args, timeout) {
            var lastArg = _.last(args);
            args[args.length - 1] = _utils.createSafeCallback(lastArg, timeout);
            _kmq.push(args);
        });

        window.analytics.usage = _makeLegacyFn(_google, 'window.analytics.usage', _google.track.event, _addCallbackToArgs);
        window.analytics.trackUsageLink = _makeLegacyFn(_google, 'window.analytics.trackUsageLink', _google.track.click);

        window.analytics.identify = _makeLegacyFn(_kissmetrics, 'window.analytics.identify', function (userId, traits) {
            if (typeof userId === 'object'){
                if (traits === undefined){
                    // the first and only argument passed was traits
                    traits = userId;
                    userId = null;
                } else {
                    // uh-oh... can't tell what the first argument was intended to be.
                    throw "Unexpected argument types";
                }
            }
            // Record identity
            if (userId !== null) {
                _kissmetrics.identify(userId);
            }
            if (traits !== undefined){
                _kissmetrics.identifyTraits(traits);
            }
        });

        window.analytics.workflow = _makeLegacyFn(_kissmetrics, 'window.analytics.workflow', _kissmetrics.track.event);
        window.analytics.track = window.analytics.workflow;

        window.analytics.trackWorkflowLink = _makeLegacyFn(_kissmetrics, ' window.analytics.trackWorkflowLink', function(element, event, properties) {
            _utils.trackClickHelper(element, function (cb) {
                _kissmetrics.track.event(event, properties, cb);
            });
        });

        analytics = window.analytics;
    }
    return {};
});

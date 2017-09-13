/* global _, Array, window */

/**
 * Instantiates the Drift analytics and customer support messaging platform.
 */
hqDefine('analytix/js/drift', function () {
    'use strict';
    var _get = hqImport('analytix/js/initial').getFn('drift'),
        _global = hqImport('analytix/js/initial').getFn('global'),
        logger = hqImport('analytix/js/logging').getLoggerForApi('Drift'),
        _utils = hqImport('analytix/js/utils'),
        _data = {},
        _drift = {};

    var __init__ = function () {
        _drift = window.driftt = window.drift = window.driftt || [];
        if (!_drift.init && !_drift.invoked ) {
            _drift.methods = [ "identify", "config", "track", "reset", "debug", "show", "ping", "page", "hide", "off", "on" ];
            _drift.factory = function (methodName) {
                return function() {
                    var methodFn = Array.prototype.slice.call(arguments);
                    methodFn.unshift(methodName);
                    _drift.push(methodFn);
                    return _drift;
                };
            };
            _.each(_drift.methods, function (methodName) {
                _drift[methodName] = _drift.factory(methodName);
            });
        }

        _drift.SNIPPET_VERSION = '0.3.1';
        _data.apiId = _get('apiId');

        if (_data.apiId) {
            _data.scriptUrl = "https://js.driftt.com/include/" + _utils.getDateHash() + "/" + _data.apiId + '.js';
            logger.verbose.log(_data.scriptUrl, "Adding Script");
            _utils.insertScript(_data.scriptUrl, logger.debug.log, {
                crossorigin: 'anonymous',
            });
        }
        _drift.on('emailCapture',function(e){
            hqImport('analytix/js/hubspot').identify({email: e.data.email});
            hqImport('analytix/js/hubspot').trackEvent('Identified via Drift');
        });
    };
    if (_global('isEnabled')) {
        __init__();
        logger.debug.log("Initialized");
    }

    // no methods just yet
    return {
        logger: logger,
    };
});
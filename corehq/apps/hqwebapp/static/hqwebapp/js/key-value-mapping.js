(function () {

var MapItem = function(item, mapping){
    var self = this;
    this.key = ko.observable(item.key);

    this.mediaValue = new AppMenuMediaManager({
        ref: {
            "path": item.value[mapping.lang],
            "icon_type": "icon-picture",
            "media_type": "Image",
            "media_class": "CommCareImage",
            "icon_class": "icon-picture"
        },
        objectMap: mapping.multimedia,
        uploadController: iconUploader,
        defaultPath: 'jr://file/commcare/image/default.png',
        inputElement: $("#" + makeSafeForCSS(this.key()))
    });

    this.value = ko.computed(function() {
        var new_value = [];
        _.each(mapping.langs, function(lang){
            if (lang == mapping.lang){
                new_value.push([lang, self.mediaValue.customPath]);
            }
            else{
                new_value.push([lang, ko.observable(item.value[lang])])
            }
        });
        return _.object(new_value);
    }, this);

    this.key.subscribe(function(newValue) {
        if(mapping.duplicatedItems.indexOf(newValue) === -1 && mapping._isItemDuplicated(newValue)) {
            mapping.duplicatedItems.push(newValue);
        }

    });

    this.key.subscribe(function(oldValue) {
        var index = mapping.duplicatedItems.indexOf(oldValue);
        if(index !== -1 && !mapping._isItemDuplicated(oldValue, 2)) {
            mapping.duplicatedItems.remove(oldValue);
        }
    }, null, "beforeChange");
};

/**
 * A MapList is an ordered list of objects, where each object has the keys "key" and "value".
 * The "value" in each item is itself be an object, mapping language codes to strings.
 */

function MapList(o) {
    var self = this;
    self.lang = o.lang;
    self.langs = [o.lang].concat(o.langs);
    self.items = ko.observableArray();
    self.duplicatedItems = ko.observableArray();
    self.values_are_icons = o.values_are_icons || false;
    self.multimedia = o.multimedia;

    self.setItems = function (items) {
        self.items(_(items).map(function (item) {
            return new MapItem(item, self);
        }));
    };
    self.setItems(o.items);

    self.backup = function (value) {
        var backup;
        for (var i = 0; i < self.langs.length; i += 1) {
            var lang = self.langs[i];
            backup = value[lang];
            if (backup && backup() !== '') {
                return {lang: lang, value: backup()};
            }
        }
        return {lang: null, value: null};
    };
    self.removeItem = function (item) {
        self.items.remove(item);
        if(!self._isItemDuplicated(ko.utils.unwrapObservable(item.key)))
            self.duplicatedItems.remove(ko.utils.unwrapObservable(item.key));
    };
    self.addItem = function () {
        var raw_item = {key: '', value: {}};
        raw_item.value[self.lang] = '';
        var item = new MapItem(raw_item, self);
        self.items.push(item);
        if(self.duplicatedItems.indexOf('') === -1 && self._isItemDuplicated('')) {
            self.duplicatedItems.push('');
        }
    };

    self._isItemDuplicated = function(key, max_counts) {
        if(typeof(max_counts) === 'undefined') max_counts = 1;
        var items = self.getItems();
        var counter = 0;
        for(var i = 0; i < items.length; i++) {
            var item = items[i];
            if(ko.utils.unwrapObservable(item.key) === key) {
                counter++;
                if(counter > max_counts) return true;
            }
        }
        return false;
    };

    self.isItemDuplicated = function(key) {
        return self.duplicatedItems.indexOf(key) !== -1;
    };

    self.getItems = function () {
        return _(self.items()).map(function (item) {
            return {
                key: ko.utils.unwrapObservable(item.key),
                value: _.object(_(item.value()).map(function (value, lang) {
                    return [lang, ko.utils.unwrapObservable(value)];
                }))
            };
        });

    };
}

uiElement.key_value_mapping = function (o) {
    var m = new MapList(o);
    m.edit = ko.observable(true);
    m.buttonText = o.buttonText || "Edit",
    m.openModal = function () {
        // create a throw-away modal every time
        // lets us create a sandbox for editing that you can cancel
        var $modalDiv = $('<div data-bind="template: \'key_value_mapping_modal\'"></div>');
        var copy = new MapList({
            lang: o.lang,
            langs: o.langs,
            items: m.getItems(),
            values_are_icons: m.values_are_icons,
            multimedia: m.multimedia
        });
        $modalDiv.koApplyBindings({
            modalTitle: o.modalTitle,
            mapList: copy,
            save: function (data, e) {
                if(copy.duplicatedItems().length > 0) {
                    e.stopImmediatePropagation();
                } else {
                    m.setItems(copy.getItems());
                }
            }
        });

        var $modal = $modalDiv.find('.modal');
        $modal.appendTo('body');
        $modal.modal('show');
        $modal.on('hidden', function () {
            $modal.remove();
        });
    };
    m.setEdit = function (edit) {
        m.edit(edit);
    };
    var $div = $('<div data-bind="template: \'key_value_mapping_template\'"></div>');
    $div.koApplyBindings(m);
    m.ui = $div;
    eventize(m);
    m.items.subscribe(function () {
        m.fire('change');
    });
    return m;
};

}());

function makeSafeForCSS(name) {
    if (!name) {
        return "";
    }
    return name.replace(/[^a-z0-9]/g, function(s) {
        var c = s.charCodeAt(0);
        if (c == 32) return '-';
        if (c >= 65 && c <= 90) return '_' + s.toLowerCase();
        return '__' + ('000' + c.toString(16)).slice(-4);
    });
}

// To overlay icon-upload modal http://stackoverflow.com/questions/19305821/multiple-modals-overlay
$(document).on('show.bs.modal', '.modal', function () {
    var zIndex = 1040 + (10 * $('.modal:visible').length);
    $(this).css('z-index', zIndex);
    setTimeout(function() {
        $('.modal-backdrop').not('.modal-stack').css('z-index', zIndex - 1).addClass('modal-stack');
    }, 0);
});
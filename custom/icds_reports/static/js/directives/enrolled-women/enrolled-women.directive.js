/* global d3, moment */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function EnrolledWomenController($scope, $routeParams, $location, $filter, demographicsService,
                                             locationsService, userLocationId, storageService) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.userLocationId = userLocationId;
    vm.filtersData = $location.search();
    vm.label = "Pregnant Women enrolled for Anganwadi Services";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/enrolled_women/map', label: 'Map View'},
        'chart': {route: '/enrolled_women/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Number of Women',
    };
    vm.chartData = null;
    vm.top_five = [];
    vm.bottom_five = [];
    vm.selectedLocations = [];
    vm.all_locations = [];
    vm.location_type = null;
    vm.loaded = false;
    vm.filters = ['gender', 'age'];

    vm.rightLegend = {
        info: 'Total number of children between the age of 0 - 6 years who are enrolled for Anganwadi Services',
    };

    vm.message = storageService.getKey('message') || false;

    $scope.$watch(function() {
        return vm.selectedLocations;
    }, function (newValue, oldValue) {
        if (newValue === oldValue || !newValue || newValue.length === 0) {
            return;
        }
        if (newValue.length === 6) {
            var parent = newValue[3];
            $location.search('location_id', parent.location_id);
            $location.search('selectedLocationLevel', 3);
            $location.search('location_name', parent.name);
            storageService.setKey('message', true);
            setTimeout(function() {
                storageService.setKey('message', false);
            }, 3000);
        }
        return newValue;
    }, true);

    vm.templatePopup = function(loc, row) {
        var valid = $filter('indiaNumbers')(row ? row.valid : 0);
        var all = $filter('indiaNumbers')(row ? row.all : 0);
        var percent = row ? d3.format('.2%')(row.valid / (row.all || 1)) : "N/A";
        return '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<div>Number of pregnant women who are enrolled for Anganwadi Services: <strong>' + valid + '</strong>' +
            '<div>Total number of pregnant women who are registered: <strong>' + all + '</strong>' +
            '<div>Percentage of registered pregnant women who are enrolled for Anganwadi Services: <strong>' + percent + '</strong>' +
            '</div>';
    };

    vm.loadData = function () {
        var loc_type = 'National';
        if (vm.location) {
            if (vm.location.location_type === 'supervisor') {
                loc_type = "Sector";
            } else {
                loc_type = vm.location.location_type.charAt(0).toUpperCase() + vm.location.location_type.slice(1);
            }
        }

        if (vm.location && _.contains(['block', 'supervisor', 'awc'], vm.location.location_type)) {
            vm.mode = 'sector';
            vm.steps['map'].label = loc_type + ' View';
        } else {
            vm.mode = 'map';
            vm.steps['map'].label = 'Map View: ' + loc_type;
        }

        vm.myPromise = demographicsService.getEnrolledWomenData(vm.step, vm.filtersData).then(function(response) {
            if (vm.step === "map") {
                vm.data.mapData = response.data.report_data;
            } else if (vm.step === "chart") {
                vm.chartData = response.data.report_data.chart_data;
                vm.all_locations = response.data.report_data.all_locations;
                vm.top_five = response.data.report_data.top_five;
                vm.bottom_five = response.data.report_data.bottom_five;
                vm.location_type = response.data.report_data.location_type;
                vm.chartTicks = vm.chartData[0].values.map(function(d) { return d.x; });
                var max = Math.ceil(d3.max(vm.chartData, function(line) {
                    return d3.max(line.values, function(d) {
                        return d.y;
                    });
                }));
                var min = Math.ceil(d3.min(vm.chartData, function(line) {
                    return d3.min(line.values, function(d) {
                        return d.y;
                    });
                }));
                var range = max - min;
                vm.chartOptions.chart.forceY = [
                    (min - range/10) < 0 ? 0 : (min - range/10),
                    (max + range/10),
                ];
            }
        });
    };

    vm.init = function() {
        var locationId = vm.filtersData.location_id || vm.userLocationId;
        if (!locationId || ["all", "null", "undefined"].indexOf(locationId) >= 0) {
            vm.loadData();
            vm.loaded = true;
            return;
        }
        locationsService.getLocation(locationId).then(function(location) {
            vm.location = location;
            vm.loadData();
            vm.loaded = true;
        });
    };

    vm.init();

    $scope.$on('filtersChange', function() {
        vm.loadData();
    });

    vm.moveToLocation = function(loc, index) {
        if (loc === 'national') {
            $location.search('location_id', '');
            $location.search('selectedLocationLevel', -1);
            $location.search('location_name', '');
        } else {
            $location.search('location_id', loc.location_id);
            $location.search('selectedLocationLevel', index);
            $location.search('location_name', loc.name);
        }
    };

    vm.chartOptions = {
        chart: {
            type: 'lineChart',
            height: 450,
            width: 1100,
            margin: {
                top: 20,
                right: 60,
                bottom: 60,
                left: 80,
            },
            x: function (d) {
                return d.x;
            },
            y: function (d) {
                return d.y;
            },
            color: d3.scale.category10().range(),
            useInteractiveGuideline: true,
            clipVoronoi: false,
            tooltips: true,
            xAxis: {
                axisLabel: '',
                showMaxMin: true,
                tickFormat: function (d) {
                    return d3.time.format('%b %Y')(new Date(d));
                },
                tickValues: function () {
                    return vm.chartTicks;
                },
                axisLabelDistance: -100,
            },

            yAxis: {
                axisLabel: '',
                tickFormat: function (d) {
                    return d3.format(",")(d);
                },
                axisLabelDistance: 20,
                forceY: [0],
            },
            callback: function (chart) {
                var tooltip = chart.interactiveLayer.tooltip;
                tooltip.contentGenerator(function (d) {
                    var day = _.find(vm.chartData[0].values, function(num) { return d3.time.format('%b %Y')(new Date(num['x'])) === d.value;});
                    return vm.tooltipContent(d.value, day);
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> Total number of pregnant women who are enrolled for Anganwadi Services',
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            },
        },
    };

    vm.tooltipContent = function(monthName, day) {
        return "<p><strong>" + monthName + "</strong></p><br/>"
            + "<div>Number of pregnant women who are enrolled for Anganwadi Services: <strong>" + $filter('indiaNumbers')(day.y) + "</strong></div>"
            + "<div>Total number of pregnant women who are registered: <strong>" + $filter('indiaNumbers')(day.all) + "</strong></div>"
            + "<div>Percentage of registered pregnant women who are enrolled for Anganwadi Services: <strong>" + d3.format('.2%')(day.y / (day.all || 1)) + "</strong></div>";
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

EnrolledWomenController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'demographicsService', 'locationsService', 'userLocationId', 'storageService'];

window.angular.module('icdsApp').directive('enrolledWomen', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: EnrolledWomenController,
        controllerAs: '$ctrl',
    };
});

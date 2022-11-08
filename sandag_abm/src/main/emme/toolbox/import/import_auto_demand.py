#//////////////////////////////////////////////////////////////////////////////
#////                                                                       ///
#//// Copyright INRO, 2016-2017.                                            ///
#//// Rights to use and modify are granted to the                           ///
#//// San Diego Association of Governments and partner agencies.            ///
#//// This copyright notice must be preserved.                              ///
#////                                                                       ///
#//// import/import_auto_demand.py                                       ///
#////                                                                       ///
#////                                                                       ///
#////                                                                       ///
#////                                                                       ///
#//////////////////////////////////////////////////////////////////////////////
#
# Imports the auto demand matrices generated from an iteration of the disaggregate
# demand models (CT-RAMP) and adds the saved disaggregated demand matrices to
# generate the total auto demand in preparation for the auto assignment.
#
# Note the matrix name mapping from the OMX file names to the Emme database names.
#
# Inputs:
#    external_zones: set of external zone IDs as a range "1-12"
#    output_dir: output directory to read the OMX files from
#    num_processors: number of processors to use in the matrix calculations
#    scenario: traffic scenario to use for reference zone system
#
# Files referenced:
#    Note: pp is time period, one of EA, AM, MD, PM, EV, vot is one of low, med, high
#    output/autoInternalExternalTrips_pp_vot.omx
#    output/autoVisitorTrips_pp_vot.omx
#    output/autoCrossBorderTrips_pp_vot.omx
#    output/autoAirportTrips.SAN_pp_vot.omx
#    output/autoAirportTrips.CDX_pp_vot.omx (if they exist)
#    output/autoTrips_pp_vot.omx
#    output/othrTrips_pp.omx (added to high vot)
#    output/TripMatrices.csv
#    output/EmptyAVTrips.omx (added to high vot)
#    output/TNCVehicleTrips_pp.omx (added to high vot)
#
# Matrix inputs:
#    pp_SOVGP_EIWORK, pp_SOVGP_EINONWORK, pp_SOVTOLL_EIWORK, pp_SOVTOLL_EINONWORK,
#    pp_HOV2HOV_EIWORK, pp_HOV2HOV_EINONWORK, pp_HOV2TOLL_EIWORK, pp_HOV2TOLL_EINONWORK,
#    pp_HOV3HOV_EIWORK, pp_HOV3HOV_EINONWORK, pp_HOV3TOLL_EIWORK, pp_HOV3TOLL_EINONWORK
#    pp_SOV_EETRIPS, pp_HOV2_EETRIPS, pp_HOV3_EETRIPS
#
# Matrix results:
#    Note: pp is time period, one of EA, AM, MD, PM, EV, v is one of L, M, H
#    pp_SOV_TR_v, pp_SOV_NT_v, pp_HOV2_v, pp_HOV3_v, pp_HOV3_v
#
# Script example:
"""
    import os
    modeller = inro.modeller.Modeller()
    main_directory = os.path.dirname(os.path.dirname(modeller.desktop.project.path))
    output_dir = os.path.join(main_directory, "output")
    external_zones = "1-12"
    num_processors = "MAX-1"
    base_scenario = modeller.scenario
    import_auto_demand = modeller.tool("sandag.import.import_auto_demand")
    import_auto_demand(external_zones, output_dir, num_processors, base_scenario)
"""
import os
import traceback as _traceback
from contextlib import contextmanager as _context

import inro.modeller as _m
import numpy
import pandas as _pandas

TOOLBOX_ORDER = 13



_join = os.path.join

dem_utils = _m.Modeller().module('sandag.utilities.demand')
gen_utils = _m.Modeller().module("sandag.utilities.general")


class ImportMatrices(_m.Tool(), gen_utils.Snapshot):

    external_zones = _m.Attribute(str)
    output_dir = _m.Attribute(unicode)
    num_processors = _m.Attribute(str)

    tool_run_msg = ""

    @_m.method(return_type=_m.UnicodeType)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    def __init__(self):
        self.external_zones = "1-12"
        project_dir = os.path.dirname(_m.Modeller().desktop.project.path)
        main_dir = os.path.dirname(project_dir)
        self.main_dir = main_dir
        self.output_dir = os.path.join(main_dir, "output")
        self.num_processors = "MAX-1"
        self.attributes = ["external_zones", "output_dir", "num_processors"]

    def page(self):
        pb = _m.ToolPageBuilder(self)
        pb.title = "Import auto demand and sum matrices"
        pb.description = """
<div style="text-align:left">
    Imports the trip matrices generated by CT-RAMP in OMX format,
    the commercial vehicle demand in CSV format,
    and adds the demand from the aggregate models for the final
    trip assignments. <br>
    A total of 90 OMX files are expected, for 5 time periods
    EA, AM, MD, PM and EV, and value-of-time level low, med or high,
    with internal matrices by SOV, HOV2, HOV3+ and toll access type:
    <ul>
        <li>autoInternalExternalTrips_pp_vot.omx</li>
        <li>autoVisitorTrips_pp_vot.omx</li>
        <li>autoCrossBorderTrips_pp_vot.omx</li>
        <li>autoAirportTrips.SAN_pp_vot.omx</li>
        <li>autoAirportTrips.CDX_pp_vot.omx (optional)</li>
        <li>autoTrips_pp_vot.omx</li>
        <li>othrTrips_pp.omx (added to high vot)</li>
        <li>EmptyAVTrips.omx (added to high vot)</li>
        <li>TNCVehicleTrips_pp.omx (added to high vot)</li>
    </ul>
    As well as one CSV file "TripMatrices.csv" for the commercial vehicle trips.
    Adds the aggregate demand from the
    external-external and external-internal demand matrices:
    <ul>
        <li>pp_SOVGP_EETRIPS, pp_HOV2HOV_EETRIPS, pp_HOV3HOV_EETRIPS</li>
        <li>pp_SOVGP_EIWORK, pp_SOVGP_EINONWORK, pp_SOVTOLL_EIWORK, pp_SOVTOLL_EINONWORK</li>
        <li>pp_HOV2HOV_EIWORK, pp_HOV2HOV_EINONWORK, pp_HOV2TOLL_EIWORK, pp_HOV2TOLL_EINONWORK</li>
        <li>pp_HOV3HOV_EIWORK, pp_HOV3HOV_EINONWORK, pp_HOV3TOLL_EIWORK, pp_HOV3TOLL_EINONWORK</li>
    </ul>
    to the time-of-day total demand matrices.
    <br>
</div>
        """
        pb.branding_text = "- SANDAG - Model"

        if self.tool_run_msg != "":
            pb.tool_run_status(self.tool_run_msg_status)
        pb.add_select_file('output_dir', 'directory',
                           title='Select output directory')
        pb.add_text_box("external_zones", title="External zones:")
        dem_utils.add_select_processors("num_processors", pb, self)
        return pb.render()

    def run(self):
        self.tool_run_msg = ""
        try:
            scenario = _m.Modeller().scenario
            self(self.output_dir, self.external_zones, self.num_processors, scenario)
            run_msg = "Tool completed"
            self.tool_run_msg = _m.PageBuilder.format_info(run_msg, escape=False)
        except Exception as error:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                error, _traceback.format_exc(error))
            raise

    @_m.logbook_trace("Create TOD auto trip tables", save_arguments=True)
    def __call__(self, output_dir, external_zones, num_processors, scenario):
        attributes = {
            "output_dir": output_dir,
            "external_zones": external_zones,
            "num_processors": num_processors}
        gen_utils.log_snapshot("Create TOD auto trip tables", str(self), attributes)

        #get parameters from sandag_abm.properties
        modeller = _m.Modeller()
        load_properties = modeller.tool('sandag.utilities.properties')
        props = load_properties(_join(self.main_dir, "conf", "sandag_abm.properties"))

        self.scenario = scenario
        self.output_dir = output_dir
        self.external_zones = external_zones
        self.num_processors = num_processors
        self.import_traffic_trips(props)
        self.import_commercial_vehicle_demand(props)
        #self.convert_light_trucks_to_pce()
        self.add_aggregate_demand()

    @_context
    def setup(self):
        emmebank = self.scenario.emmebank
        self._matrix_cache = {}
        with gen_utils.OMXManager(self.output_dir, "%sTrips%s%s.omx") as omx_manager:
            try:
                yield omx_manager
            finally:
                for name, value in self._matrix_cache.iteritems():
                    matrix = emmebank.matrix(name)
                    matrix.set_numpy_data(value, self.scenario.id)

    def set_data(self, name, value):
        if name in self._matrix_cache:
            value = value + self._matrix_cache[name]
        self._matrix_cache[name] = value

    @_m.logbook_trace("Import CT-RAMP traffic trips from OMX")
    def import_traffic_trips(self, props):
        title = "Import CT-RAMP traffic trips from OMX report"
        report = _m.PageBuilder(title)

        taxi_da_share = props["Taxi.da.share"]
        taxi_s2_share = props["Taxi.s2.share"]
        taxi_s3_share = props["Taxi.s3.share"]
        taxi_pce = props["Taxi.passengersPerVehicle"]
        tnc_single_da_share = props["TNC.single.da.share"]
        tnc_single_s2_share = props["TNC.single.s2.share"]
        tnc_single_s3_share = props["TNC.single.s3.share"]
        tnc_single_pce = props["TNC.single.passengersPerVehicle"]
        tnc_shared_da_share = props["TNC.shared.da.share"]
        tnc_shared_s2_share = props["TNC.shared.s2.share"]
        tnc_shared_s3_share = props["TNC.shared.s3.share"]
        tnc_shared_pce = props["TNC.shared.passengersPerVehicle"]
        av_share = props["Mobility.AV.Share"]

        periods = ["_EA", "_AM", "_MD", "_PM", "_EV"]
        vot_bins = ["_low", "_med", "_high"]
        mode_shares = [
            ("mf%s_SOV_TR_H", {
                "TAXI": taxi_da_share / taxi_pce
            }),
            ("mf%s_HOV2_H",   {
                "TAXI": taxi_s2_share / taxi_pce
            }),
            ("mf%s_HOV3_H",   {
                "TAXI": taxi_s3_share / taxi_pce
            }),
        ]

        with self.setup() as omx_manager:
            # SOV transponder "TRPDR" = "TR" and non-transponder "NOTRPDR" = "NT"
            for period in periods:
                for vot in vot_bins:
                    # SOV non-transponder demand
                    matrix_name = "mf%s_SOV_NT_%s" % (period[1:], vot[1].upper())
                    logbook_label = "Import auto from OMX SOVNOTRPDR to matrix %s" % (matrix_name)
                    resident_demand = omx_manager.lookup(("auto", period, vot), "SOVNOTRPDR%s" % period)
                    visitor_demand = omx_manager.lookup(("autoVisitor", period, vot), "SOV%s" % period)
                    cross_border_demand = omx_manager.lookup(("autoCrossBorder", period, vot), "SOV%s" % period)
                    # NOTE: No non-transponder airport or internal-external demand
                    total_ct_ramp_trips = (
                        resident_demand + visitor_demand + cross_border_demand)
                    dem_utils.demand_report([
                            ("resident", resident_demand),
                            ("cross_border", cross_border_demand),
                            ("visitor", visitor_demand),
                            ("total", total_ct_ramp_trips)
                        ],
                        logbook_label, self.scenario, report)
                    self.set_data(matrix_name, total_ct_ramp_trips)

                    # SOV transponder demand
                    matrix_name = "mf%s_SOV_TR_%s" % (period[1:], vot[1].upper())
                    logbook_label = "Import auto from OMX SOVTRPDR to matrix %s" % (matrix_name)
                    resident_demand = omx_manager.lookup(("auto", period, vot), "SOVTRPDR%s" % period)
                    # NOTE: No transponder visitor or cross-border demand
                    airport_demand = omx_manager.lookup(("autoAirport", ".SAN" + period, vot), "SOV%s" % period)
                    if omx_manager.file_exists(("autoAirport", ".CBX" + period, vot)):
                        airport_demand += omx_manager.lookup(("autoAirport", ".CBX" + period, vot), "SOV%s" % period)
                    internal_external_demand = omx_manager.lookup(("autoInternalExternal", period, vot), "SOV%s" % period)

                    total_ct_ramp_trips = (
                        resident_demand + airport_demand + internal_external_demand)
                    dem_utils.demand_report([
                            ("resident", resident_demand),
                            ("airport", airport_demand),
                            ("internal_external", internal_external_demand),
                            ("total", total_ct_ramp_trips)
                        ],
                        logbook_label, self.scenario, report)
                    self.set_data(matrix_name, total_ct_ramp_trips)

                    # HOV2 and HOV3 demand
                    matrix_name_map = [
                        ("mf%s_HOV2_%s",    "SR2%s"),
                        ("mf%s_HOV3_%s",    "SR3%s")
                    ]
                    for matrix_name_tmplt, omx_name in matrix_name_map:
                        matrix_name = matrix_name_tmplt % (period[1:], vot[1].upper())
                        logbook_label = "Import auto from OMX %s to matrix %s" % (omx_name[:3], matrix_name)
                        resident_demand = (
                            omx_manager.lookup(("auto", period, vot), omx_name % ("TRPDR" + period))
                            + omx_manager.lookup(("auto", period, vot), omx_name % ("NOTRPDR" + period)))
                        visitor_demand = omx_manager.lookup(("autoVisitor", period, vot), omx_name % period)
                        cross_border_demand = omx_manager.lookup(("autoCrossBorder", period, vot), omx_name % period)
                        airport_demand = omx_manager.lookup(("autoAirport", ".SAN" + period, vot), omx_name % period)
                        if omx_manager.file_exists(("autoAirport", ".CBX" + period, vot)):
                            airport_demand += omx_manager.lookup(("autoAirport", ".CBX" + period, vot), omx_name % period)
                        internal_external_demand = omx_manager.lookup(("autoInternalExternal", period, vot), omx_name % period)

                        total_ct_ramp_trips = (
                            resident_demand + visitor_demand + cross_border_demand + airport_demand + internal_external_demand)
                        dem_utils.demand_report([
                                ("resident", resident_demand),
                                ("cross_border", cross_border_demand),
                                ("visitor", visitor_demand),
                                ("airport", airport_demand),
                                ("internal_external", internal_external_demand),
                                ("total", total_ct_ramp_trips)
                            ],
                            logbook_label, self.scenario, report)
                        self.set_data(matrix_name, total_ct_ramp_trips)

                # add TNC and TAXI demand to vot="high"
                for matrix_name_tmplt, share in mode_shares:
                    matrix_name = matrix_name_tmplt % period[1:]
                    logbook_label = "Import othr from TAXI, empty AV, and TNC to matrix %s" % (matrix_name)
                    resident_taxi_demand = (
                        omx_manager.lookup(("othr", period, ""), "TAXI" + period) * share["TAXI"])
                    visitor_taxi_demand = (
                        omx_manager.lookup(("othrVisitor", period, ""), "TAXI" + period) * share["TAXI"])
                    cross_border_taxi_demand = (
                        omx_manager.lookup(("othrCrossBorder", period, ""), "TAXI" + period) * share["TAXI"])
                    # airport SAN
                    airport_taxi_demand = (
                        omx_manager.lookup(("othrAirport", ".SAN", period), "TAXI" + period) * share["TAXI"])
                    # airport CBX (optional)
                    if omx_manager.file_exists(("othrAirport", ".CBX", period)):
                        airport_taxi_demand += (
                            omx_manager.lookup(("othrAirport",".CBX", period), "TAXI" + period) * share["TAXI"])
                    internal_external_taxi_demand = (
                        omx_manager.lookup(("othrInternalExternal", period, ""), "TAXI" + period) * share["TAXI"])

                    #AV routing models and TNC fleet model demand
                    empty_av_demand = omx_manager.lookup(("EmptyAV","",""), "EmptyAV%s" % period)
                    tnc_demand_0 = omx_manager.lookup(("TNCVehicle","",period), "TNC%s_0" % period)
                    tnc_demand_1 = omx_manager.lookup(("TNCVehicle","",period), "TNC%s_1" % period)
                    tnc_demand_2 = omx_manager.lookup(("TNCVehicle","",period), "TNC%s_2" % period)
                    tnc_demand_3 = omx_manager.lookup(("TNCVehicle","",period), "TNC%s_3" % period)

                    #AVs: no driver. No AVs: driver
                    #AVs: 0 and 1 passenger would be SOV. there will be empty vehicles as well. No AVs: 0 passanger would be SOV
                    #AVs: 2 passenger would be HOV2. No AVs: 1 passenger would be HOV2
                    #AVs: 3 passenger would be HOV3. No AVs: 2 and 3 passengers would be HOV3
                    if (av_share>0):
                        if (matrix_name_tmplt[5:-2] == "SOV_TR"):
                            av_demand = empty_av_demand + tnc_demand_0 + tnc_demand_1
                        elif (matrix_name_tmplt[5:-2] == "HOV2"):
                            av_demand = tnc_demand_2
                        else:
                            av_demand = tnc_demand_3
                    else:
                        if (matrix_name_tmplt[5:-2] == "SOV_TR"):
                            av_demand = tnc_demand_0
                        elif (matrix_name_tmplt[5:-2] == "HOV2"):
                            av_demand = tnc_demand_1
                        else:
                            av_demand = tnc_demand_2 + tnc_demand_3

                    total_ct_ramp_trips = (
                        resident_taxi_demand + visitor_taxi_demand + cross_border_taxi_demand
                        + airport_taxi_demand + internal_external_taxi_demand + av_demand)
                    dem_utils.demand_report([
                            ("resident_taxi", resident_taxi_demand),
                            ("visitor_taxi", visitor_taxi_demand),
                            ("cross_border_taxi", cross_border_taxi_demand),
                            ("airport_taxi", airport_taxi_demand),
                            ("internal_external_taxi", internal_external_taxi_demand),
                            ("av_fleet", av_demand),
                            ("total", total_ct_ramp_trips)
                        ],
                        logbook_label, self.scenario, report)
                    self.set_data(matrix_name, total_ct_ramp_trips)
        _m.logbook_write(title, report.render())

    @_m.logbook_trace('Import commercial vehicle demand')
    def import_commercial_vehicle_demand(self, props):
        scale_factor = props["cvm.scale_factor"]
        scale_light = props["cvm.scale_light"]
        scale_medium = props["cvm.scale_medium"]
        scale_heavy = props["cvm.scale_heavy"]
        share_light = props["cvm.share.light"]
        share_medium = props["cvm.share.medium"]
        share_heavy = props["cvm.share.heavy"]

        scenario = self.scenario
        emmebank = scenario.emmebank

        mapping = {}
        periods = ["EA", "AM", "MD", "PM", "EV"]
        # The SOV demand is modified in-place, which was imported
        # prior from the CT-RAMP demand
        # The truck demand in vehicles is copied from separate matrices
        for index, period in enumerate(periods):
            mapping["CVM_%s:LNT" % period] = {
                "orig": "%s_SOV_TR_H" % period,
                "dest": "%s_SOV_TR_H" % period,
                "pce": 1.0,
                "scale": scale_light[index],
                "share": share_light,
                "period": period
            }
            mapping["CVM_%s:INT" % period] = {
                "orig": "%s_TRK_L_VEH" % period,
                "dest": "%s_TRK_L" % period,
                "pce": 1.3,
                "scale": scale_medium[index],
                "share": share_medium,
                "period": period
            }
            mapping["CVM_%s:MNT" % period] = {
                "orig": "%s_TRK_M_VEH" % period,
                "dest": "%s_TRK_M" % period,
                "pce": 1.5,
                "scale": scale_medium[index],
                "share": share_medium,
                "period": period
            }
            mapping["CVM_%s:HNT" % period] = {
                "orig": "%s_TRK_H_VEH" % period,
                "dest": "%s_TRK_H" % period,
                "pce": 2.5,
                "scale": scale_heavy[index],
                "share": share_heavy,
                "period": period
            }
        with _m.logbook_trace('Load starting SOV and truck matrices'):
            for key, value in mapping.iteritems():
                value["array"] = emmebank.matrix(value["orig"]).get_numpy_data(scenario)

        with _m.logbook_trace('Processing CVM from TripMatrices.csv'):
            path = os.path.join(self.output_dir, "TripMatrices.csv")
            table = _pandas.read_csv(path)
            for key, value in mapping.iteritems():
                cvm_array = table[key].values.reshape((4996, 4996))     # reshape method deprecated since v 0.19.0, yma, 2/12/2019
                #factor in cvm demand by the scale factor used in trip generation
                cvm_array = cvm_array/scale_factor
                #scale trips to take care of underestimation
                cvm_array = cvm_array * value["scale"]

                #add remaining share to the correspnding truck matrix
                value["array"] = value["array"] + (cvm_array * (1-value["share"]))

            #add cvm truck vehicles to light-heavy trucks
            for key, value in mapping.iteritems():
                period = value["period"]
                cvm_vehs = ['L','M','H']
                if key == "CVM_%s:INT" % period:
                    for veh in cvm_vehs:
                        key_new = "CVM_%s:%sNT" % (period, veh)
                        value_new = mapping[key_new]
                        if value_new["share"] != 0.0:
                            cvm_array = table[key_new].values.reshape((4996, 4996))
                            cvm_array = cvm_array/scale_factor
                            cvm_array = cvm_array * value_new["scale"]
                            value["array"] = value["array"] + (cvm_array * value_new["share"])
        matrix_unique = {}
        with _m.logbook_trace('Save SOV matrix and convert CV and truck vehicle demand to PCEs for assignment'):
            for key, value in mapping.iteritems():
                matrix = emmebank.matrix(value["dest"])
                array = value["array"] * value["pce"]
                if (matrix in matrix_unique.keys()):
                    array = array + emmebank.matrix(value["dest"]).get_numpy_data(scenario)
                matrix.set_numpy_data(array, scenario)
                matrix_unique[matrix] = 1

    @_m.logbook_trace('Convert light truck vehicle demand to PCEs for assignment')
    def convert_light_trucks_to_pce(self):
        matrix_calc = dem_utils.MatrixCalculator(self.scenario, self.num_processors)
        # Calculate PCEs for trucks
        periods = ["EA", "AM", "MD", "PM", "EV"]
        mat_trucks = ['TRK_L']
        pce_values = [1.3]
        for period in periods:
            with matrix_calc.trace_run("Period %s" % period):
                for name, pce in zip(mat_trucks, pce_values):
                    demand_name = 'mf%s_%s' % (period, name)
                    matrix_calc.add(demand_name, '(%s_VEH * %s).max.0' % (demand_name, pce))

    @_m.logbook_trace('Add aggregate demand')
    def add_aggregate_demand(self):
        matrix_calc = dem_utils.MatrixCalculator(self.scenario, self.num_processors)
        periods = ["EA", "AM", "MD", "PM", "EV"]
        vots = ["L", "M", "H"]
        # External-internal trips DO have transponder
        # all SOV trips go to SOVTP
        with matrix_calc.trace_run("Add external-internal trips to auto demand"):
            modes = ["SOVGP", "SOVTOLL", "HOV2HOV", "HOV2TOLL", "HOV3HOV", "HOV3TOLL"]
            modes_assign = {"SOVGP":    "SOV_TR",
                            "SOVTOLL":  "SOV_TR",
                            "HOV2HOV":  "HOV2",
                            "HOV2TOLL": "HOV2",
                            "HOV3HOV":  "HOV3",
                            "HOV3TOLL": "HOV3"}
            for period in periods:
                for mode in modes:
                    for vot in vots:
                        # Segment imported demand into 3 equal parts for VOT Low/Med/High
                        assign_mode = modes_assign[mode]
                        params = {'p': period, 'm': mode, 'v': vot, 'am': assign_mode}
                        matrix_calc.add("mf%s_%s_%s" % (period, assign_mode, vot),
                             "mf%(p)s_%(am)s_%(v)s "
                             "+ (1.0/3.0)*mf%(p)s_%(m)s_EIWORK "
                             "+ (1.0/3.0)*mf%(p)s_%(m)s_EINONWORK" % params)

        # External - external faster with single-processor as number of O-D pairs is so small (12 X 12)
        # External-external trips do not have transpnder
        # all SOV trips go to SOVNTP
        matrix_calc.num_processors = 0
        with matrix_calc.trace_run("Add external-external trips to auto demand"):
            modes = ["SOV", "HOV2", "HOV3"]
            for period in periods:
                for mode in modes:
                    for vot in vots:
                        # Segment imported demand into 3 equal parts for VOT Low/Med/High
                        params = {'p': period, 'm': mode, 'v': vot}
                        if (mode == "SOV"):
                            matrix_calc.add(
                                "mf%(p)s_%(m)s_NT_%(v)s" % params,
                                "mf%(p)s_%(m)s_NT_%(v)s + (1.0/3.0)*mf%(p)s_%(m)s_EETRIPS" % params,
                                {"origins": self.external_zones, "destinations": self.external_zones})
                        else:
                            matrix_calc.add(
                                "mf%(p)s_%(m)s_%(v)s" % params,
                                "mf%(p)s_%(m)s_%(v)s + (1.0/3.0)*mf%(p)s_%(m)s_EETRIPS" % params,
                                {"origins": self.external_zones, "destinations": self.external_zones})

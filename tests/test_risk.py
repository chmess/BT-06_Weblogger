import copy
import unittest
from datetime import datetime,timedelta,timezone
from backend.common.risk import analyze,validate_options

DEFAULT={'air_threshold':70,'surface_threshold':80,'hysteresis':2,'minimum_minutes':20,'surface_mode':'none','surface_value':None}
START=datetime(2026,1,1,tzinfo=timezone.utc)

def rows(minutes,humidities,temperatures=None):
    return [{'Zeitstempel':(START+timedelta(minutes=m)).isoformat(),'Temperatur':str(temperatures[i] if temperatures else 20),'Feuchte':'' if rh is None else str(rh)} for i,(m,rh) in enumerate(zip(minutes,humidities))]


class RiskTests(unittest.TestCase):
    def analyze(self,data,**changes):return analyze(iter(data),10,{**DEFAULT,**changes})

    def test_phase_requires_duration_and_does_not_count_transition_to_low_value(self):
        data=rows([0,10,20,30],[75,75,75,60]);original=copy.deepcopy(data)
        result=self.analyze(data);air=result['air']
        self.assertEqual(air['observed_seconds'],1800);self.assertEqual(air['above_threshold_seconds'],1200)
        self.assertEqual(air['qualified_phase_count'],1);self.assertEqual(air['longest_phase_seconds'],1200)
        self.assertEqual(air['phases'][0]['end_ms'],round((START+timedelta(minutes=20)).timestamp()*1000))
        self.assertFalse(air['phases'][0]['right_censored']);self.assertEqual(data,original)
        self.assertIsNone(result['surface']);self.assertIsNone(result['condensation'])

    def test_hysteresis_band_is_distinct_from_strict_threshold_time(self):
        air=self.analyze(rows([0,10,20,30],[70,69,68,67]))['air']
        self.assertEqual(air['release_pct'],68);self.assertEqual(air['longest_phase_seconds'],1200)
        self.assertEqual(air['above_threshold_seconds'],0);self.assertEqual(air['qualified_phase_count'],1)
        self.assertEqual(self.analyze(rows([0,10,20],[69,69,69]))['air']['phase_count'],0)

    def test_gap_breaks_phases_and_does_not_help_minimum_duration(self):
        air=self.analyze(rows([0,10,100,110],[80]*4),minimum_minutes=15)['air']
        self.assertEqual(air['phase_count'],2);self.assertEqual(air['qualified_phase_count'],0)
        self.assertEqual(air['observed_seconds'],1200);self.assertEqual(air['unknown_seconds'],5400)
        self.assertEqual(air['above_threshold_seconds'],1200);self.assertEqual(air['status'],'incomplete')
        self.assertEqual(air['phases'][0]['end_reason'],'data_gap')

    def test_invalid_values_break_the_chain_without_invalidating_air_due_to_temperature(self):
        air=self.analyze(rows([0,10,20,30,40],[80,None,80,80,60]),minimum_minutes=10)['air']
        self.assertEqual(air['unknown_seconds'],1200);self.assertEqual(air['qualified_phase_count'],1)
        self.assertEqual(air['invalid_samples'],1);self.assertEqual(air['phase_count'],2)
        data=rows([0,10],[90,90],[70,70]);result=self.analyze(data,surface_mode='fixed',surface_value=15)
        self.assertEqual(result['air']['observed_seconds'],600);self.assertEqual(result['surface']['observed_seconds'],0)
        self.assertEqual(result['surface']['invalid_samples'],2)

    def test_requested_edges_empty_and_single_sample_are_not_treated_as_known(self):
        bounds={'start':START.isoformat(),'end':(START+timedelta(minutes=40)).isoformat()}
        result=analyze(rows([10,20],[80,80]),10,DEFAULT,**bounds)['air']
        self.assertEqual(result['observed_seconds'],600);self.assertEqual(result['unknown_seconds'],1800)
        self.assertEqual(result['coverage_fraction'],0.25)
        for data in ([],rows([20],[80])):
            result=analyze(data,10,DEFAULT,**bounds)['air']
            self.assertEqual(result['status'],'insufficient_data');self.assertEqual(result['unknown_seconds'],2400)
            self.assertEqual(result['qualified_phase_count'],0)

    def test_surface_assumptions_are_separate_and_condensation_is_not_clamped_away(self):
        data=rows([0,10,20],[60]*3)
        fixed=self.analyze(data,surface_mode='fixed',surface_value=15)
        delta=self.analyze(data,surface_mode='delta',surface_value=5)
        self.assertEqual(fixed['air']['qualified_phase_count'],0)
        self.assertEqual(fixed['surface']['qualified_phase_count'],1)
        self.assertEqual(fixed['surface'],delta['surface'])
        self.assertEqual(fixed['condensation']['above_threshold_samples'],0)
        cold=self.analyze(data,surface_mode='fixed',surface_value=5)
        self.assertEqual(cold['condensation']['qualified_phase_count'],1)
        self.assertGreater(cold['condensation']['phases'][0]['peak_pct'],100)
        outside=self.analyze(rows([0,10],[90,90],[-40,-40]),surface_mode='delta',surface_value=10)
        self.assertEqual(outside['surface']['invalid_samples'],2)

    def test_report_is_bounded_but_counts_every_phase(self):
        data=rows(list(range(303)),[80,80,60]*101)
        result=analyze(data,1,{**DEFAULT,'minimum_minutes':1})['air']
        self.assertEqual(result['phase_count'],101);self.assertEqual(len(result['phases']),100)
        self.assertEqual(result['qualified_phase_count'],101);self.assertEqual(result['omitted_phases'],1)

    def test_criteria_ordering_and_timestamp_validation(self):
        for changes in ({'air_threshold':0},{'surface_threshold':101},{'hysteresis':70},{'minimum_minutes':True},
                        {'minimum_minutes':float('nan')},{'surface_mode':'guess'},{'surface_value':15},
                        {'surface_mode':'fixed','surface_value':True},{'surface_mode':'delta','surface_value':-1}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate_options({**DEFAULT,**changes})
        for data in (rows([0,0],[80,80]),rows([10,0],[80,80])):
            with self.assertRaises(ValueError):self.analyze(data)
        data=rows([0,10],[80,80]);data[0]['Zeitstempel']='2026-01-01T01:00:00+01:00'
        self.assertEqual(self.analyze(data)['air']['observed_seconds'],600)

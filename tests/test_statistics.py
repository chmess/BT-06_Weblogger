import copy
import json
import unittest
from datetime import datetime,timedelta,timezone
from backend.common.statistics import summarize

START=datetime(2026,1,1,tzinfo=timezone.utc)

def rows(minutes,temperatures,humidity=None):
    return [{'Zeitstempel':(START+timedelta(minutes=m)).isoformat(),'Temperatur':'' if value is None else str(value),'Feuchte':str(humidity[i] if humidity else 50)} for i,(m,value) in enumerate(zip(minutes,temperatures))]


class StatisticsTests(unittest.TestCase):
    def test_extrema_means_and_original_values_are_preserved(self):
        data=rows([0,10,20],[10,20,30]);before=copy.deepcopy(data)
        result=summarize(iter(data),10);metric=result['metrics']['temperature_c']
        self.assertEqual(result['raw_count'],3);self.assertEqual(metric['valid_samples'],3)
        self.assertEqual(metric['minimum']['value'],10);self.assertEqual(metric['maximum']['value'],30)
        self.assertEqual(metric['sample_mean'],20);self.assertEqual(metric['time_weighted_mean'],20)
        self.assertEqual(metric['observed_seconds'],1200);self.assertEqual(metric['unknown_seconds'],0)
        self.assertEqual(metric['coverage_fraction'],1);self.assertEqual(data,before)

    def test_irregular_sampling_has_distinct_sample_and_time_means(self):
        metric=summarize(rows([0,10,30],[0,10,30]),20)['metrics']['temperature_c']
        self.assertAlmostEqual(metric['sample_mean'],40/3);self.assertAlmostEqual(metric['time_weighted_mean'],15)
        self.assertEqual(metric['observed_seconds'],1800)

    def test_gaps_and_missing_channels_are_not_bridged(self):
        result=summarize(rows([0,10,110,120],[10,20,30,40]),10);metric=result['metrics']['temperature_c']
        self.assertEqual(result['gap_count'],1);self.assertEqual(result['largest_sample_interval_seconds'],6000)
        self.assertEqual(metric['time_weighted_mean'],25);self.assertEqual(metric['observed_seconds'],1200)
        self.assertEqual(metric['unknown_seconds'],6000);self.assertEqual(metric['status'],'incomplete')
        result=summarize(rows([0,10,20],[20,None,30],[50,60,70]),10)
        self.assertEqual(result['metrics']['temperature_c']['sample_mean'],25)
        self.assertIsNone(result['metrics']['temperature_c']['time_weighted_mean'])
        self.assertEqual(result['metrics']['humidity_pct']['observed_seconds'],1200)
        self.assertEqual(result['metrics']['dew_point_c']['observed_seconds'],0)

    def test_derived_values_respect_zero_humidity_and_model_range(self):
        result=summarize(rows([0,10,20],[20,20,70],[0,50,50]),10)
        self.assertEqual(result['metrics']['temperature_c']['valid_samples'],3)
        self.assertEqual(result['metrics']['dew_point_c']['valid_samples'],1)
        self.assertIsNone(result['metrics']['dew_point_c']['time_weighted_mean'])
        density=result['metrics']['absolute_humidity_g_m3']
        self.assertEqual(density['valid_samples'],2);self.assertEqual(density['minimum']['value'],0)
        self.assertEqual(density['observed_seconds'],600)

    def test_empty_single_and_requested_edges_do_not_create_time_coverage(self):
        bounds={'start':START.isoformat(),'end':(START+timedelta(minutes=60)).isoformat()}
        for data in ([],rows([10],[20])):
            metric=summarize(data,10,**bounds)['metrics']['temperature_c']
            self.assertEqual(metric['observed_seconds'],0);self.assertEqual(metric['unknown_seconds'],3600)
            self.assertIsNone(metric['time_weighted_mean']);self.assertEqual(metric['status'],'insufficient_data')
        metric=summarize(rows([10,20],[20,20]),10,**bounds)['metrics']['temperature_c']
        self.assertEqual(metric['unknown_seconds'],3000)

    def test_invalid_time_order_intervals_and_nonfinite_values(self):
        for data in (rows([0,0],[20,20]),rows([10,0],[20,20])):
            with self.assertRaises(ValueError):summarize(data,10)
        for interval in (0,True,float('nan')):
            with self.assertRaises(ValueError):summarize([],interval)
        metric=summarize(rows([0,10],[float('nan'),float('inf')],[101,50]),10)['metrics']['temperature_c']
        self.assertEqual(metric['missing_samples'],2);json.dumps(metric,allow_nan=False)
        data=rows([0,10],[20,30]);data[0]['Zeitstempel']='2026-01-01T01:00:00+01:00'
        self.assertEqual(summarize(data,10)['metrics']['temperature_c']['observed_seconds'],600)

    def test_large_finite_samples_do_not_overflow_running_means(self):
        metric=summarize(rows([0,10,20],[1e308,1e308,1e308]),10)['metrics']['temperature_c']
        self.assertAlmostEqual(metric['sample_mean']/1e308,1)
        self.assertAlmostEqual(metric['time_weighted_mean']/1e308,1)
        json.dumps(metric,allow_nan=False)

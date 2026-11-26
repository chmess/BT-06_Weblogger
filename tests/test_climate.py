import json
import unittest
from datetime import datetime,timedelta,timezone
from backend.common.climate import air_values,calculate,saturation_pressure
from backend.common.storage import chart_data


class ClimateTests(unittest.TestCase):
    def calculate(self,t=20,rh=50,surface=None):
        return calculate({'temperature_c':t,'humidity_pct':rh,'surface_temperature_c':surface})

    def test_reference_room_conditions_and_cold_surface(self):
        value=self.calculate(surface=10)
        self.assertAlmostEqual(value['dew_point_c'],9.26,delta=0.02)
        self.assertAlmostEqual(value['absolute_humidity_g_m3'],8.62,delta=0.02)
        self.assertAlmostEqual(value['surface_relative_humidity_pct'],95.13,delta=0.03)
        self.assertAlmostEqual(value['critical_surface_70_c'],14.67,delta=0.02)
        self.assertAlmostEqual(value['critical_surface_80_c'],12.62,delta=0.02)
        self.assertFalse(value['condensation_possible'])
        self.assertTrue(self.calculate(surface=5)['condensation_possible'])
        self.assertIsNone(self.calculate()['condensation_possible'])
        self.assertGreater(self.calculate(surface=5)['surface_relative_humidity_pct'],100)

    def test_saturation_and_threshold_invariants_including_model_boundaries(self):
        for t in (-45,-20,0,20,60):
            with self.subTest(t=t):
                value=self.calculate(t,100,t)
                self.assertAlmostEqual(value['dew_point_c'],t,places=9)
                self.assertAlmostEqual(value['surface_dew_point_margin_c'],0,places=9)
                self.assertAlmostEqual(value['surface_relative_humidity_pct'],100,places=9)
        self.assertAlmostEqual(self.calculate(0,100)['absolute_humidity_g_m3'],4.85,delta=0.02)
        self.assertAlmostEqual(self.calculate(20,80)['critical_surface_80_c'],20,places=9)
        self.assertAlmostEqual(self.calculate(20,70)['critical_surface_70_c'],20,places=9)

    def test_missing_zero_and_out_of_range_never_become_fabricated_dew_points(self):
        zero=self.calculate(rh=0,surface=0)
        self.assertIsNone(zero['dew_point_c']);self.assertEqual(zero['absolute_humidity_g_m3'],0)
        self.assertFalse(zero['condensation_possible']);self.assertIsNone(zero['critical_surface_80_c'])
        self.assertIsNone(self.calculate(-40,1)['dew_point_c'])
        self.assertEqual(air_values(70,50)['status'],'outside_model_range')
        for t,rh in ((None,50),(20,None),(True,50),(20,False),(20,float('nan')),(10**500,50)):
            with self.subTest(t=t,rh=rh):self.assertIsNone(air_values(t,rh)['dew_point_c'])
        json.dumps(zero,allow_nan=False)

    def test_calculator_rejects_unknown_fields_bad_types_and_bounds(self):
        for t,rh,surface in ((61,50,None),(-46,50,None),(20,101,None),(20,-1,None),('20',50,None),(True,50,None),(20,50,True),(20,50,61),(float('inf'),50,None),(20,10**500,None)):
            with self.subTest(t=t,rh=rh,surface=surface),self.assertRaises(ValueError):self.calculate(t,rh,surface)
        with self.assertRaises(ValueError):calculate({'temperature_c':20})

    def test_decimation_preserves_derived_extrema_and_alignment(self):
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        rows=[{'Zeitstempel':(start+timedelta(minutes=i)).isoformat(),'Temperatur':'10','Feuchte':'40'} for i in range(200)]
        rows[10].update(Temperatur='30',Feuchte='20')
        rows[20].update(Temperatur='5',Feuchte='90')
        rows[123].update(Temperatur='25',Feuchte='80')
        result=chart_data(rows,1,budget=8)
        self.assertTrue(all(len(point)==3 for point in result['points']))
        self.assertEqual([p[0] for p in result['points']],[p[0] for p in result['climate']['points']])
        peak=int((start+timedelta(minutes=123)).timestamp()*1000)
        self.assertIn(peak,[p[0] for p in result['climate']['points']])
        expected=air_values(25,80)['dew_point_c']
        self.assertAlmostEqual(result['climate']['max_dew_point_c'],expected)

    def test_empty_missing_and_gap_points_remain_missing_in_derived_series(self):
        self.assertIsNone(chart_data([],1)['climate']['latest'])
        rows=[{'Zeitstempel':'2026-01-01T00:00:00Z','Temperatur':'20','Feuchte':'50'},
              {'Zeitstempel':'2026-01-01T00:10:00Z','Temperatur':'70','Feuchte':'50'}]
        result=chart_data(rows,1)
        self.assertEqual(result['latest'][1],70)
        self.assertEqual(result['climate']['latest']['status'],'outside_model_range')
        self.assertTrue(any(p[1:]==[None,None] for p in result['climate']['points']))
        self.assertEqual(result['climate']['points'][-1][1:],[None,None])

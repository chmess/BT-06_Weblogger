import copy
import csv
import io
import unittest
from backend.common.export import CALCULATED,CALC_METADATA,EXPORT_METADATA,options,selected_fields,project_rows
from backend.common.storage import FIELDS,csv_text
from backend.common.history_store import HISTORY_FIELDS
from backend.common.history_timezones import ASSIGNED_FIELDS


def row(t='20,00',rh='50,00'):
    value={key:'' for key in FIELDS}
    value.update(Schema='1',DatensatzID='synthetic',Zeitstempel='2026-01-01T00:00:00Z',Temperatur=t,Feuchte=rh,Quelle='Simulation',Messstelle='demo-room',Qualitaet='SYNTHETISCH')
    return value


class ExportTests(unittest.TestCase):
    def test_selection_preserves_original_values_and_mandatory_provenance(self):
        original=row();before=copy.deepcopy(original)
        fields=selected_fields(FIELDS,'Temperatur')
        result=list(project_rows([original],fields))[0]
        self.assertEqual(result['Temperatur'],'20,00');self.assertNotIn('Feuchte',result)
        for key in options(FIELDS)['required_fields']:self.assertIn(key,result)
        self.assertEqual(result['Exporttyp'],'Spaltenauswahl');self.assertEqual(original,before)

    def test_derived_values_have_units_decimal_comma_model_and_status(self):
        fields=selected_fields(FIELDS,'Taupunkt_C,AbsoluteFeuchte_g_m3',True)
        result=list(project_rows([row()],fields,True))[0]
        self.assertAlmostEqual(float(result['Taupunkt_C'].replace(',','.')),9.2552,places=3)
        self.assertAlmostEqual(float(result['AbsoluteFeuchte_g_m3'].replace(',','.')),8.62,delta=0.02)
        self.assertEqual(result['Berechnungsstatus'],'ok');self.assertEqual(result['Exporttyp'],'AbgeleitetesKlima')
        self.assertTrue(result['Berechnungsmodell']);self.assertNotIn('Temperatur',result)
        records=list(csv.DictReader(io.StringIO(csv_text([result],fields)),delimiter=';'))
        self.assertEqual(records,[result])

    def test_zero_missing_and_out_of_model_are_not_fabricated(self):
        fields=selected_fields(FIELDS,climate=True)
        zero,missing,outside=list(project_rows([row(rh='0'),row(rh=''),row(t='70')],fields,True))
        self.assertEqual(zero['Taupunkt_C'],'');self.assertEqual(zero['AbsoluteFeuchte_g_m3'],'0,0000')
        self.assertEqual(zero['Berechnungsstatus'],'zero_humidity')
        for value in (missing,outside):self.assertTrue(all(value[key]=='' for key in CALCULATED))
        self.assertEqual(outside['Berechnungsstatus'],'outside_model_range')

    def test_invalid_or_ambiguous_field_selection_is_rejected(self):
        for text,climate in (('',False),('Temperatur,Temperatur',False),('unknown',False),('Taupunkt_C',False),('Temperatur',True),('Berechnungsstatus',True)):
            with self.subTest(text=text,climate=climate),self.assertRaises(ValueError):selected_fields(FIELDS,text,climate)
        with self.assertRaises(ValueError):selected_fields(FIELDS,climate=1)

    def test_device_and_assigned_time_metadata_cannot_be_removed(self):
        original={key:'' for key in HISTORY_FIELDS+ASSIGNED_FIELDS};original.update(row())
        original.update(Zeitstempel='',GeraeteSekunden='1700000000',Geraetekalender='2026-01-01T00:00:00',Zeitbasis='GERAETEZEIT_UNGEPRUEFT',Firmware='2.05',Zeitzuordnung='BEREICH_NICHT_BESTAETIGT')
        fields=selected_fields(HISTORY_FIELDS+ASSIGNED_FIELDS,'Taupunkt_C',True)
        result=list(project_rows([original],fields,True))[0]
        for key in ['GeraeteSekunden','Geraetekalender','Zeitbasis','Firmware']+ASSIGNED_FIELDS: self.assertEqual(result[key],original[key])
        self.assertEqual(result['Zeitstempel'],'');self.assertEqual(result['ZugeordneteZeit'],'')
        self.assertTrue(set(CALC_METADATA+EXPORT_METADATA)<=set(fields))

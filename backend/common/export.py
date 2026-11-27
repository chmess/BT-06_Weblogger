"""Explicit selection/derived CSV copies; the default original export is unchanged."""
from .climate import MODEL,air_values

EXPORT_METADATA=['ExportSchema','Exporttyp']
CALCULATED={'Taupunkt_C':'dew_point_c','AbsoluteFeuchte_g_m3':'absolute_humidity_g_m3',
            'Saettigungsdampfdruck_hPa':'saturation_pressure_hpa','WasserdampfPartialdruck_hPa':'vapor_pressure_hpa'}
CALC_METADATA=['Berechnungsmodell','Berechnungsstatus']
LABELS={'Taupunkt_C':'Taupunkt (°C)','AbsoluteFeuchte_g_m3':'Absolute Feuchte (g/m³)',
        'Saettigungsdampfdruck_hPa':'Sättigungsdampfdruck (hPa)','WasserdampfPartialdruck_hPa':'Wasserdampf-Partialdruck (hPa)'}


def options(original_fields):
    required=[key for key in original_fields if key in {'Logger','Schema','DatensatzID','Zeitstempel','Quelle','Messstelle','Qualitaet',
              'GeraeteSekunden','Geraetekalender','Zeitbasis','Firmware','ZugeordneteZeit','BestaetigteZeitzone','Zeitzuordnung'}]
    return {'original_fields':list(original_fields),'required_fields':required,'export_metadata':EXPORT_METADATA,
            'calculated_fields':list(CALCULATED),'calculated_metadata':CALC_METADATA,'labels':LABELS,'model':MODEL}


def selected_fields(original_fields,field_text=None,climate=False):
    if not isinstance(climate,bool):raise ValueError('Ungültiger Berechnungsmodus.')
    available=list(original_fields)+EXPORT_METADATA+(list(CALCULATED)+CALC_METADATA if climate else [])
    if field_text is None:chosen=list(original_fields)+(list(CALCULATED) if climate else [])
    else:
        if not isinstance(field_text,str):raise ValueError('Spaltenliste muss Text sein.')
        chosen=field_text.split(',')
        if not chosen or len(set(chosen))!=len(chosen) or any(key not in available for key in chosen):raise ValueError('Leere, unbekannte oder doppelte Exportspalten.')
    if climate and not set(chosen)&set(CALCULATED):raise ValueError('Mindestens eine berechnete Größe auswählen.')
    required=options(original_fields)['required_fields']+EXPORT_METADATA+(CALC_METADATA if climate else [])
    wanted=set(chosen+required)
    return [key for key in available if key in wanted]


def project_rows(rows,fields,climate=False):
    for original in rows:
        row={**original,'ExportSchema':'1','Exporttyp':'AbgeleitetesKlima' if climate else 'Spaltenauswahl'}
        if climate:
            temperature=float(original['Temperatur'].replace(',','.')) if original['Temperatur'] else None
            humidity=float(original['Feuchte'].replace(',','.')) if original['Feuchte'] else None
            value=air_values(temperature,humidity)
            row.update(Berechnungsmodell=MODEL['id'],Berechnungsstatus=value['status'])
            for column,key in CALCULATED.items():row[column]='' if value[key] is None else f'{value[key]:.4f}'.replace('.',',')
        yield {key:row[key] for key in fields}

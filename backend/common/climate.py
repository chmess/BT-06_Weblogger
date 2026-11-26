"""Derived humidity values over liquid water; original measurements stay unchanged.

Magnus coefficients and validity: Universität Hamburg, Wettermast description,
A.10 (2026). Absolute humidity: ideal gas relation, Vaisala HMP155 guide.
See docs/KLIMA.md for units, references and limitations.
"""
import math

MODEL = {'id':'magnus-water-17.62-243.12-v1','temperature_range_c':[-45,60],
         'reference':'liquid_water','pressure_enhancement':False}


def finite_number(value):
    try:return type(value) in (int,float) and math.isfinite(value)
    except OverflowError:return False


def saturation_pressure(temperature_c):
    return 6.112*math.exp(17.62*temperature_c/(243.12+temperature_c))


def inverse_pressure(pressure_hpa):
    if pressure_hpa<=0:return None
    alpha=math.log(pressure_hpa/6.112)
    result=243.12*alpha/(17.62-alpha)
    return min(60,max(-45,result)) if -45-1e-10<=result<=60+1e-10 else None


def air_values(temperature_c,humidity_pct):
    result={'status':'missing_or_invalid_input','dew_point_c':None,'absolute_humidity_g_m3':None,
            'saturation_pressure_hpa':None,'vapor_pressure_hpa':None}
    if not finite_number(temperature_c) or not finite_number(humidity_pct) or not 0<=humidity_pct<=100:return result
    if not -45<=temperature_c<=60:return {**result,'status':'outside_model_range'}
    saturation=saturation_pressure(temperature_c);pressure=saturation*humidity_pct/100
    dew_point=inverse_pressure(pressure)
    result.update(status='ok' if dew_point is not None else 'zero_humidity' if humidity_pct==0 else 'dew_point_outside_model_range',
                  dew_point_c=dew_point,absolute_humidity_g_m3=216.679*pressure/(temperature_c+273.15),
                  saturation_pressure_hpa=saturation,vapor_pressure_hpa=pressure)
    return result


def calculate(request):
    if not isinstance(request,dict) or set(request)!={'temperature_c','humidity_pct','surface_temperature_c'}:
        raise ValueError('Lufttemperatur, relative Feuchte und optionale Oberflächentemperatur erforderlich.')
    temperature,humidity,surface=(request[key] for key in ('temperature_c','humidity_pct','surface_temperature_c'))
    if not finite_number(temperature) or not -45<=temperature<=60:raise ValueError('Lufttemperatur: −45 bis 60 °C erforderlich.')
    if not finite_number(humidity) or not 0<=humidity<=100:raise ValueError('Relative Feuchte: 0 bis 100 % erforderlich.')
    if surface is not None and (not finite_number(surface) or not -45<=surface<=60):raise ValueError('Oberflächentemperatur: −45 bis 60 °C oder leer erforderlich.')
    result=air_values(temperature,humidity);pressure=result['vapor_pressure_hpa']
    surface_rh=100*pressure/saturation_pressure(surface) if surface is not None else None
    return {**result,'model':MODEL,'inputs':dict(request),
            'critical_surface_70_c':inverse_pressure(pressure/0.7),
            'critical_surface_80_c':inverse_pressure(pressure/0.8),
            'surface_relative_humidity_pct':surface_rh,
            'surface_dew_point_margin_c':surface-result['dew_point_c'] if surface is not None and result['dew_point_c'] is not None else None,
            'condensation_possible':surface_rh>=100 if surface_rh is not None else None}

"""Genera tabla de consumo real con valores de cierre mensual y semanal."""
from pathlib import Path
import json,calendar,datetime
from importar_tabla_monitor import normalize

P = Path('.')
national = json.loads((P / 'bigdata.json').read_text(encoding='utf-8'))
macro = json.loads((P / 'data.json').read_text(encoding='utf-8'))['series']
geo_index = P / 'bigdata_geo/index.json'
geo = json.loads(geo_index.read_text(encoding='utf-8'))['groups'] if geo_index.exists() else {}
regions={
 'ES-AN':['ES-AL','ES-CA','ES-CO','ES-GR','ES-H','ES-J','ES-MA','ES-SE'],
 'ES-AR':['ES-HU','ES-TE','ES-Z'],'ES-AS':['ES-O'],'ES-CN':['ES-GC','ES-TF'],'ES-CB':['ES-S'],
 'ES-CL':['ES-AV','ES-BU','ES-LE','ES-P','ES-SA','ES-SG','ES-SO','ES-VA','ES-ZA'],
 'ES-CM':['ES-AB','ES-CR','ES-CU','ES-GU','ES-TO'],'ES-CT':['ES-B','ES-GI','ES-L','ES-T'],
 'ES-CE':['ES-CE'],'ES-VC':['ES-A','ES-CS','ES-V'],'ES-EX':['ES-BA','ES-CC'],
 'ES-GA':['ES-C','ES-LU','ES-OR','ES-PO'],'ES-IB':['ES-PM'],'ES-RI':['ES-LO'],'ES-MD':['ES-M'],
 'ES-ML':['ES-ML'],'ES-MC':['ES-MU'],'ES-NC':['ES-NA'],'ES-PV':['ES-VI','ES-BI','ES-SS']}
city_province={'01':'ES-VI','03':'ES-A','08':'ES-B','14':'ES-CO','18':'ES-GR','28':'ES-M','29':'ES-MA','30':'ES-MU','33':'ES-O','35':'ES-GC','36':'ES-PO','41':'ES-SE','46':'ES-V','48':'ES-BI','50':'ES-Z'}
labels=[('Total coicops','Indicador Big Data de consumo total'),('Food & Beverage','Alimentos y bebidas no alcohólicas'),('Alcohol & Tobacco','Bebidas alcohólicas y tabaco'),('Clothing & FootWear','Calzado y textil'),('Housing & Utilities','Energía del hogar'),('Furnishing & House Equipment','Mobiliario y mantenimiento del hogar'),('Health','Salud'),('Transport','Transporte'),('Info & Communication','Información y comunicaciones'),('Leisure','Ocio, deporte y cultura'),('Education','Educación'),('Restaurant & Hotels','Restaurantes y hoteles'),('Insurance & Fin. Service','Seguros y servicios financieros'),('Other','Otros bienes y servicios')]
def compact(data,scale=100):
 monthly={};weekly={}
 for d,v,*_ in data:
  try: dt=datetime.date.fromisoformat(d);v=float(v)*scale
  except (ValueError,TypeError):continue
  if dt.day==calendar.monthrange(dt.year,dt.month)[1]:monthly[d[:7]]=round(v,6)
  if dt.weekday()==6:weekly[d]=round(v,6)
 return {'monthly':monthly,'weekly':weekly}
rows=[]
for key,title in [('ch_yoy','Consumo de los hogares (INE)'),('icm_yoy','Índice de comercio al por menor (INE)')]:
 s=macro[key];months={}
 for d,v,*_ in s['data']:
  year,month=int(d[:4]),int(d[5:7]);month=month+2 if s['freq']=='Q' else month;months[f'{year:04d}-{month:02d}']=v
 rows.append({'group':'nacional','level':0,'label':title,'source':'INE','monthly':months,'weekly':{}})
for col,label in labels:
 s=next((s for s in national['series'] if s['label']==f'Consumo · {col} · Real'),None)
 if s:rows.append({'group':'nacional','level':0 if col=='Total coicops' else 1,'label':label,'source':'BBVA Research',**compact(s['data'])})
province={a['id']:a for a in geo.get('Provincial', [])};cities={}
for a in geo.get('Urbano', []):cities.setdefault(city_province.get(a['id'][:2],''),[]).append(a)
def territory(a,level):
 filename=next((f for f in a['files'] if '/real/' in f),None)
 if not filename:return
 src=json.loads((P/'bigdata_geo'/filename).read_text(encoding='utf-8'));s=next((s for s in src['series'] if ' · Total Consumo · Real' in s['label']),None)
 if s:rows.append({'group':'territorial','level':level,'label':a['label'],'source':'BBVA Research',**compact(s['data'])})
used=set()
for area in geo.get('CCAA', []):
 territory(area,0)
 for code in regions.get(area['id'],[]):
  if code in province:
   territory(province[code],1);used.add(code)
   for city in cities.get(code,[]):territory(city,2)
assert set(province)==used, 'Provincias sin asignar: '+str(set(province)-used)


def row_key(row):
    return row['group'], row['level'], normalize(row['label'])


def apply_monitor(rows, monitor_rows):
    by_key = {row_key(row): row for row in rows}
    previous = None
    for published in monitor_rows:
        key = row_key(published)
        current = by_key.get(key)
        if current is None:
            if previous is not None and previous['group'] == published['group']:
                index = rows.index(previous) + 1
            else:
                index = next((i for i, row in enumerate(rows) if row['group'] == published['group']), len(rows))
            rows.insert(index, published)
            by_key[key] = published
            current = published
        else:
            for frequency in ('monthly', 'weekly'):
                current[frequency].update(published[frequency])
        previous = current


monitor = national.get('monitor')
if monitor:
    apply_monitor(rows, monitor['rows'])
result={'title':'España: Indicadores de consumo','unit':'%','note':'Indicador real; variación interanual de la media móvil de 28 días. Cierre de mes y semana.','rows':rows}
if monitor:
    result['monitor'] = {key: monitor.get(key) for key in ('source', 'updated_at', 'sha256')}
(P/'bigdata_heatmap.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf8')
print('Filas nacionales:',sum(r['group']=='nacional' for r in rows),'territoriales:',sum(r['group']=='territorial' for r in rows))

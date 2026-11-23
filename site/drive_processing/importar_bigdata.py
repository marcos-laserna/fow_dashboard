from pathlib import Path
from datetime import datetime,date
import openpyxl,math,json,re,sys
if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != '--manual'):
 raise SystemExit('Uso: python importar_bigdata.py /ruta/Alta_Frecuencia_Espana.xlsx [--manual]')
manual = len(sys.argv) == 3
source=Path(sys.argv[1]);dest=Path('manual_workbook.json' if manual else 'bigdata.json')
w=openpyxl.load_workbook(source,read_only=True,data_only=True)
config=[('ESP_Consumo','Consumo',{'Type %','Isocode','Date','EN','ES'}),('Inversion_España','Inversión',{'Type','Date','Country'}),('España_Activ_Sectorial','Actividad sectorial',{'Type','Date'})]
if manual:
 config = config[:1]
series=[]
for sheet,group,excluded in config:
 rows=w[sheet].iter_rows(values_only=True); headers=list(next(rows)); di=next(i for i,h in enumerate(headers) if str(h).strip().lower()=='date');ti=next(i for i,h in enumerate(headers) if str(h).strip().lower().startswith('type')); cols=[(i,str(h).strip()) for i,h in enumerate(headers) if h is not None and str(h).strip() not in excluded]
 if manual:
  cols = [(i, name) for i, name in cols if name == 'Total coicops']
 bucket={}
 for row in rows:
  if di>=len(row) or ti>=len(row):continue
  date_value=row[di];typ=str(row[ti] or '').strip()
  if typ not in ('Nominal','Real') or not date_value:continue
  if isinstance(date_value,(datetime,date)): day=date_value.strftime('%Y-%m-%d')
  else:
   day=str(date_value).strip()[:10]
   if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day):continue
  for i,name in cols:
   if i>=len(row) or row[i] is None:continue
   val=row[i]
   try:
    if isinstance(val,str): val=float(val.strip().replace(',','.'))
    else:val=float(val)
    if not math.isfinite(val):continue
   except (ValueError,TypeError):continue
   key=(group,typ,name);bucket.setdefault(key,{})[day]=val
 for j,((g,typ,name),data) in enumerate(bucket.items()):
  if not data:continue
  if manual:
   series.append({
    'id': f'manual_consumo_total_{typ.lower()}',
    'label': f'Consumo total · {typ.lower()}',
    'unit': '%', 'freq': 'D', 'source': 'Google Drive · Alta Frecuencia - España',
    'data': [[day, value * 100, 0] for day, value in sorted(data.items())],
   })
  else:
   series.append({'id':f'{sheet}_{j}', 'label':f'{g} · {name} · {typ}', 'group':g,'unit':'valor original de la hoja','freq':'D','source':'BBVA Research','data':[[d,v,0] for d,v in sorted(data.items())]})
output={'source':'BBVA Research · Alta Frecuencia - España','sheet_names':[x[0] for x in config], 'series':series}
if manual:
 if {item['id'] for item in series} != {'manual_consumo_total_real', 'manual_consumo_total_nominal'}:
  raise ValueError('ESP_Consumo: faltan datos de consumo total real o nominal')
 manifest = source.with_name('manifest.json')
 if manifest.is_file():
  metadata = json.loads(manifest.read_text(encoding='utf-8-sig'))
  output['updated_at'] = metadata.get('updated_at')
  output['sha256'] = next((item.get('sha256') for item in metadata['files'] if item['file'] == source.name), None)
dest.write_text(json.dumps(output,ensure_ascii=False,separators=(',',':')),encoding='utf-8');print('Series:',len(series),'observaciones:',sum(len(s['data']) for s in series),'bytes:',dest.stat().st_size)

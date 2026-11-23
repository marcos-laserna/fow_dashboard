import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path

SOURCE = Path('drive_data/bigdata/Datos_informe.csv')
GEO_ROOT = Path('bigdata_geo')
NATIONAL_OUTPUT = Path('bigdata.json')
CONSUMPTION_COLUMNS = {
    'ES': 'Total coicops',
    **dict(zip((f'CAT{i}' for i in range(1, 14)), (
        'Food & Beverage', 'Alcohol & Tobacco', 'Clothing & FootWear', 'Housing & Utilities',
        'Furnishing & House Equipment', 'Health', 'Transport', 'Info & Communication',
        'Leisure', 'Education', 'Restaurant & Hotels', 'Insurance & Fin. Service', 'Other',
    ))),
}
LEVELS = {
    'ccaa': ('CCAA', 'ccaa'),
    'provincia': ('Provincial', 'provincial'),
    'ciudad': ('Urbano', 'urbano'),
}


def number(value):
    text = str(value or '').strip().replace('\u00a0', '').replace(' ', '')
    if not text:
        return None
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.') if text.rfind(',') > text.rfind('.') else text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        result = float(text)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def safe_date(value):
    try:
        return date.fromisoformat(str(value or '').strip()[:10]).isoformat()
    except ValueError:
        return None


def merge_national_series(consumption):
    payload = json.loads(NATIONAL_OUTPUT.read_text(encoding='utf-8'))
    by_label = {series['label']: series for series in payload['series']}
    for code, observations in consumption.items():
        label = f'Consumo · {CONSUMPTION_COLUMNS[code]} · Real'
        series = by_label.get(label)
        if series is None:
            series = {
                'id': f'drive_consumo_{code.lower()}', 'label': label, 'group': 'Consumo',
                'unit': 'fracción interanual', 'freq': 'D', 'data': [],
            }
            payload['series'].append(series)
        first, last = min(observations), max(observations)
        history = {day: value for day, value, *_ in series['data'] if day < first or day > last}
        history.update(observations)
        series['source'] = 'BBVA Research · Datos_informe.csv'
        series['data'] = [[day, value, 0] for day, value in sorted(history.items())]
    NATIONAL_OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def main():
    if not SOURCE.is_file():
        raise SystemExit(f'Missing Drive export: {SOURCE}')

    groups = {label: {} for label, _ in LEVELS.values()}
    consumption = {}
    required = {'fecha', 'nivel', 'codigo', 'nombre', 'nombre_mostrado', 'valor'}
    with SOURCE.open('r', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        headers = {str(name or '').strip().lower() for name in (reader.fieldnames or [])}
        missing = required - headers
        if missing:
            raise ValueError('Datos_informe.csv is missing columns: ' + ', '.join(sorted(missing)))
        for row_number, row in enumerate(reader, start=2):
            level = str(row.get('nivel') or '').strip().lower()
            code = str(row.get('codigo') or '').strip()
            if level in ('nacional', 'categoria') and code in CONSUMPTION_COLUMNS:
                day, value = safe_date(row.get('fecha')), number(row.get('valor'))
                if day and value is not None:
                    consumption.setdefault(code, {})[day] = value
                continue
            if level not in LEVELS:
                continue
            group_label, folder = LEVELS[level]
            day = safe_date(row.get('fecha'))
            value = number(row.get('valor'))
            name = str(row.get('nombre_mostrado') or row.get('nombre') or code).strip()
            if not day or value is None or not code or not name:
                raise ValueError(f'Invalid territory observation at CSV row {row_number}')
            key = (code, name)
            series = groups[group_label].setdefault(key, {})
            series[day] = value

    index = {'groups': {label: [] for label, _ in LEVELS.values()}}
    for group_label, areas in groups.items():
        _, folder = next(v for v in LEVELS.values() if v[0] == group_label)
        for (code, name), observations in sorted(areas.items(), key=lambda item: (item[0][1].casefold(), item[0][0])):
            token = hashlib.sha256(f'{group_label}|{code}|{name}|real'.encode('utf-8')).hexdigest()[:20]
            relative = Path(folder) / 'real' / f'{token}.json'
            destination = GEO_ROOT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            series = {
                'id': 'drive_geo_' + token,
                'label': f'{group_label} · {name} · Total Consumo · Real',
                'group': group_label,
                'unit': 'fracción interanual',
                'freq': 'D',
                'source': 'BBVA Research · Datos_informe.csv',
                'data': [[day, value, 0] for day, value in sorted(observations.items())],
            }
            destination.write_text(json.dumps({'series': [series]}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
            index['groups'][group_label].append({'id': code, 'label': name, 'files': [relative.as_posix()]})

    if not any(index['groups'].values()):
        raise ValueError('Datos_informe.csv did not contain any CCAA, province, or city observations')
    (GEO_ROOT / 'index.json').write_text(json.dumps(index, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    if consumption:
        merge_national_series(consumption)
    counts = ', '.join(f'{name}: {len(areas)}' for name, areas in index['groups'].items())
    print('Updated Big Data geography index — ' + counts)


if __name__ == '__main__':
    main()

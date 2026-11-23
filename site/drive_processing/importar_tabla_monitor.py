"""Import the published monthly and weekly observations from Drive."""
import csv
import hashlib
import io
import json
import math
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

MONITOR_CSV = Path('drive_data/bigdata/Tabla_monitor.csv')
MONTHS = dict(zip('ene feb mar abr may jun jul ago sep oct nov dic'.split(), range(1, 13)))
SECTIONS = {'nacional': 'nacional', 'ccaa / provincias / ciudades': 'territorial'}
NATIONAL_LABELS = {
    'consumo privado nacional ine': 'Consumo de los hogares (INE)',
    'indice de comercio al por menor ine': 'Índice de comercio al por menor (INE)',
    'indicador big data de consumo total': 'Indicador Big Data de consumo total',
    'energia del hogar luz agua gas': 'Energía del hogar',
    'mobiliario electrodomesticos y mantenimiento vivienda': 'Mobiliario y mantenimiento del hogar',
    'cuidado personal proteccion social y bienes y servicios diver': 'Otros bienes y servicios',
}


def normalize(text):
    plain = ''.join(char for char in unicodedata.normalize('NFD', text.casefold())
                    if not unicodedata.combining(char))
    return ' '.join(re.findall(r'[a-z0-9]+', plain))


def parse_columns(cells):
    monthly = {}
    for index, cell in enumerate(cells[1:], start=1):
        match = re.fullmatch(r'([a-z]{3}) (\d{2}|\d{4})', normalize(cell))
        if match and match[1] in MONTHS:
            year = int(match[2]) + (2000 if len(match[2]) == 2 else 0)
            monthly[index] = date(year, MONTHS[match[1]], 1)
    if not monthly:
        raise ValueError('Tabla_monitor.csv: missing monthly columns')

    columns = {i: ('monthly', d.isoformat()[:7]) for i, d in monthly.items()}
    anchor = max(monthly.values())
    previous_week = None
    for index, cell in enumerate(cells[1:], start=1):
        if index in columns or not cell.strip():
            continue
        week = re.fullmatch(r'\d{1,2}(?: [a-z]{3})? (\d{1,2}) ([a-z]{3})', normalize(cell))
        if not week or week[2] not in MONTHS:
            raise ValueError(f'Tabla_monitor.csv: invalid period {cell!r}')
        month = MONTHS[week[2]]
        if previous_week:
            year = previous_week.year + (month < previous_week.month)
        else:
            year = anchor.year + (anchor.month - month + 6) // 12
        week_end = date(year, month, int(week[1]))
        if previous_week and not 0 < (week_end - previous_week).days <= 31:
            raise ValueError(f'Tabla_monitor.csv: weekly dates out of sequence at {cell!r}')
        previous_week = week_end
        columns[index] = ('weekly', week_end.isoformat())
    return columns


def unpack_row(cells):
    if len(cells) != 1:
        return cells
    wrapped = cells[0]
    if wrapped.startswith('"'):
        return next(csv.reader([wrapped]))
    label, separator, values = wrapped.partition(',"')
    if separator:
        # Wrapped exports may leave commas in the row label unquoted.
        return [label, *next(csv.reader(['"' + values]))]
    return cells


def source_updated_at(source):
    manifest = source.with_name('manifest.json')
    if not manifest.is_file():
        return None
    files = json.loads(manifest.read_text(encoding='utf-8-sig')).get('files', [])
    return next((item.get('updated_at') for item in files if item.get('file') == source.name), None)


def read_monitor(source):
    raw = source.read_bytes()
    stream = io.StringIO(raw.decode('utf-8-sig'), newline='')
    rows = []
    group = None
    with stream:
        for row_number, fields in enumerate(csv.reader(stream), start=1):
            cells = unpack_row(fields)
            if not cells or not cells[0].strip():
                continue
            raw_label = cells[0].expandtabs(3)
            section = SECTIONS.get(raw_label.strip().casefold())
            if section:
                group = section
                columns = parse_columns(cells)
                continue
            if not group or not any(i < len(cells) and cells[i].strip() for i in columns):
                continue

            label = raw_label.strip().rstrip('*').strip()
            indent = len(raw_label) - len(raw_label.lstrip())
            level = min(2, indent // 3) if group == 'territorial' else int(indent > 0)
            if group == 'nacional':
                label = NATIONAL_LABELS.get(normalize(label), label)
            row = {
                'group': group, 'level': level, 'label': label,
                'source': 'INE' if label.endswith('(INE)') else 'BBVA Research',
                'monthly': {}, 'weekly': {},
            }
            for i, (frequency, period) in columns.items():
                value = cells[i].strip() if i < len(cells) else ''
                if value in ('', '-', '—'):
                    row[frequency][period] = None
                    continue
                try:
                    percent = float(value.replace(',', '.')) * 100
                except ValueError:
                    percent = math.nan
                if not math.isfinite(percent):
                    print(f'Tabla_monitor.csv:{row_number}: ignored {value!r} for {label!r} at {period}',
                          file=sys.stderr)
                    continue
                row[frequency][period] = round(percent, 6)
            rows.append(row)
    if not any(value is not None for row in rows
               for frequency in ('monthly', 'weekly') for value in row[frequency].values()):
        raise ValueError('Tabla_monitor.csv: no numeric consumption observations found')
    return {
        'source': source.name,
        'updated_at': source_updated_at(source),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'rows': rows,
    }


if __name__ == '__main__':
    path = Path('bigdata.json')
    payload = json.loads(path.read_text(encoding='utf-8'))
    payload['monitor'] = read_monitor(MONITOR_CSV)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print('Filas del monitor de Drive:', len(payload['monitor']['rows']))

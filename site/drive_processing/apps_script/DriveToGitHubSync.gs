/**
 * Sync Big Data, high-frequency, and optional Turkey data to drive_processing.
 * Store the GitHub credential only in Apps Script Project Properties.
 * Required property: GITHUB_TOKEN
 * Optional property: DRIVE_TURKEY_FOLDER_ID (configure when that folder exists)
 */
const CONFIG = {
  owner: 'marcos-laserna',
  repo: 'fow_dashboard',
  branch: 'main',
  bigDataFolderId: '1thGWH7iyzwmC3YDjMHf1J_vwmPfNpm8H',
  highFrequencyFolderId: '1U8giN5bJ4tJLAtVf_rjlxLu9s6qGr3u2',
  highFrequencySpreadsheetId: '1lqU0EbQHoDATmfNNOl7yodFTve6MYxCHLjCoRczsVy8',
  bigDataRepoFolder: 'site/drive_processing/drive_data/bigdata',
  highFrequencyRepoPath: 'site/drive_processing/drive_data/high_frequency/alta_frecuencia.xlsx',
  turkeyRepoFolder: 'site/drive_processing/manual_csv',
  turkeyFolderProperty: 'DRIVE_TURKEY_FOLDER_ID',
  bigDataCsvNames: ['Tabla_monitor.csv', 'Datos_informe.csv'],
  highFrequencySpreadsheetName: 'Alta Frecuencia - España'
};

function syncDriveToGitHub() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const props = PropertiesService.getScriptProperties();
    const token = props.getProperty('GITHUB_TOKEN');
    if (!token) throw new Error('Set GITHUB_TOKEN in Apps Script Project Properties.');
    syncBigDataFolder_(props, token);
    syncHighFrequencyWorkbook_(props, token);
    syncTurkeyFolder_(props, token);
  } finally {
    lock.releaseLock();
  }
}

/** Run once in Apps Script to create a five-minute Drive polling trigger. */
function installDriveSyncTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === 'syncDriveToGitHub') ScriptApp.deleteTrigger(trigger);
  });
  ScriptApp.newTrigger('syncDriveToGitHub').timeBased().everyMinutes(5).create();
}

function syncBigDataFolder_(props, token) {
  const folder = DriveApp.getFolderById(CONFIG.bigDataFolderId);
  const filesByName = {};
  const iterator = folder.getFiles();
  while (iterator.hasNext()) {
    const file = iterator.next();
    const key = file.getName().toLowerCase();
    if (CONFIG.bigDataCsvNames.some(function (name) { return name.toLowerCase() === key; })) {
      if (filesByName[key]) throw new Error('Duplicate Big Data source file: ' + file.getName());
      filesByName[key] = file;
    }
  }
  const missing = CONFIG.bigDataCsvNames.filter(function (name) { return !filesByName[name.toLowerCase()]; });
  if (missing.length) throw new Error('Big Data folder is missing: ' + missing.join(', '));

  const manifestFiles = [];
  let latest = null;
  CONFIG.bigDataCsvNames.forEach(function (name) {
    const file = filesByName[name.toLowerCase()];
    const csv = file.getBlob().getDataAsString('UTF-8').replace(/^\uFEFF/, '');
    const path = CONFIG.bigDataRepoFolder + '/' + name;
    uploadTextIfChanged_(file, path, csv, 'Sync Big Data source: ' + name, props, token);
    const updated = file.getLastUpdated();
    if (!latest || updated.getTime() > latest.getTime()) latest = updated;
    manifestFiles.push({ file: name, updated_at: updated.toISOString(), size: file.getSize() });
  });
  const manifest = { version: 1, updated_at: latest ? latest.toISOString() : null, files: manifestFiles };
  putGithubFile_(CONFIG.bigDataRepoFolder + '/manifest.json', JSON.stringify(manifest, null, 2) + '\n', 'Update Big Data Drive manifest', token);
  Logger.log('Big Data Drive sync complete: ' + manifestFiles.length + ' CSV files.');
}

function syncHighFrequencyWorkbook_(props, token) {
  const folder = DriveApp.getFolderById(CONFIG.highFrequencyFolderId);
  const candidates = [];
  const iterator = folder.getFiles();
  while (iterator.hasNext()) {
    const file = iterator.next();
    if (file.getId() === CONFIG.highFrequencySpreadsheetId && file.getName() === CONFIG.highFrequencySpreadsheetName &&
        file.getMimeType() === 'application/vnd.google-apps.spreadsheet') candidates.push(file);
  }
  if (!candidates.length) throw new Error('Could not find the configured Alta Frecuencia Google Sheet in its Drive folder.');
  const file = candidates[0];
  const updated = file.getLastUpdated();
  const modifiedProperty = 'DRIVE_SYNC_MODIFIED_' + file.getId();
  let size = Number(props.getProperty('DRIVE_SYNC_SIZE_' + file.getId()) || 0);
  if (props.getProperty(modifiedProperty) !== String(updated.getTime())) {
    const bytes = exportSpreadsheetXlsx_(file.getId());
    uploadBytesIfChanged_(file, CONFIG.highFrequencyRepoPath, bytes, 'Sync high-frequency workbook', props, token);
    size = bytes.length;
    props.setProperty('DRIVE_SYNC_SIZE_' + file.getId(), String(size));
    props.setProperty(modifiedProperty, String(updated.getTime()));
  }
  const manifest = {
    version: 1,
    updated_at: updated.toISOString(),
    files: [{ file: 'alta_frecuencia.xlsx', source_title: file.getName(), source_updated_at: updated.toISOString(), size: size }]
  };
  putGithubFile_('site/drive_processing/drive_data/high_frequency/manifest.json', JSON.stringify(manifest, null, 2) + '\n', 'Update high-frequency Drive manifest', token);
  Logger.log('High-frequency workbook sync complete.');
}

function syncTurkeyFolder_(props, token) {
  const folderId = props.getProperty(CONFIG.turkeyFolderProperty);
  if (!folderId) {
    Logger.log('Turkey Drive folder is not configured yet; set ' + CONFIG.turkeyFolderProperty + ' when its route is ready.');
    return;
  }
  const folder = DriveApp.getFolderById(folderId);
  const iterator = folder.getFiles();
  const manifestFiles = [];
  const seenIds = {};
  let latest = null;
  while (iterator.hasNext()) {
    const file = iterator.next();
    const originalName = file.getName();
    if (!/\.csv$/i.test(originalName)) continue;
    const csv = file.getBlob().getDataAsString('UTF-8').replace(/^\uFEFF/, '');
    const parsed = parseSeriesCsv_(csv, originalName);
    const id = 'turquia_' + parsed.id.replace(/^turquia_/, '');
    if (seenIds[id]) throw new Error('Two Turkey CSV files produce the same series ID: ' + id);
    seenIds[id] = true;
    const githubName = id + '.csv';
    uploadTextIfChanged_(file, CONFIG.turkeyRepoFolder + '/' + githubName, csv, 'Sync Turkey CSV: ' + id, props, token);
    const updated = file.getLastUpdated();
    if (!latest || updated.getTime() > latest.getTime()) latest = updated;
    manifestFiles.push({ id: id, file: githubName, label: parsed.label, unit: parsed.unit, freq: parsed.freq,
      block: 'manual', source: 'Google Drive · Turquía CSV', updated_at: updated.toISOString() });
  }
  manifestFiles.sort(function (a, b) { return a.id.localeCompare(b.id); });
  const manifest = { version: 1, updated_at: latest ? latest.toISOString() : null, files: manifestFiles };
  putGithubFile_(CONFIG.turkeyRepoFolder + '/manifest.json', JSON.stringify(manifest, null, 2) + '\n', 'Update Turkey CSV manifest', token);
  Logger.log('Turkey Drive sync complete: ' + manifestFiles.length + ' series.');
}

function exportSpreadsheetXlsx_(fileId) {
  const url = 'https://www.googleapis.com/drive/v3/files/' + encodeURIComponent(fileId) +
    '/export?mimeType=' + encodeURIComponent('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  const response = UrlFetchApp.fetch(url, { method: 'get', headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() }, muteHttpExceptions: true });
  if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) {
    throw new Error('Could not export the high-frequency Google Sheet (HTTP ' + response.getResponseCode() + '): ' + response.getContentText().slice(0, 300));
  }
  return response.getContent();
}

function uploadTextIfChanged_(file, path, content, message, props, token) {
  const digest = sha256Hex_(Utilities.newBlob(content, 'text/plain').getBytes());
  const property = 'DRIVE_SYNC_SHA256_' + file.getId();
  if (props.getProperty(property) === digest) return false;
  putGithubFile_(path, content, message, token);
  props.setProperty(property, digest);
  return true;
}

function uploadBytesIfChanged_(file, path, bytes, message, props, token) {
  const digest = sha256Hex_(bytes);
  const property = 'DRIVE_SYNC_SHA256_' + file.getId();
  if (props.getProperty(property) === digest) return false;
  putGithubBytes_(path, bytes, message, token);
  props.setProperty(property, digest);
  return true;
}

function sha256Hex_(bytes) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes)
    .map(function (value) { return ('0' + (value & 255).toString(16)).slice(-2); }).join('');
}

function parseSeriesCsv_(text, fileName) {
  const firstLine = text.split(/\r?\n/).find(function (line) { return line.trim(); }) || '';
  const delimiter = firstLine.split(';').length > firstLine.split(',').length ? ';' : ',';
  const rows = Utilities.parseCsv(text, delimiter).filter(function (row) {
    return row.some(function (cell) { return String(cell).trim() !== ''; });
  });
  if (rows.length < 2) throw new Error(fileName + ' needs a header and at least one observation.');

  const norm = function (value) {
    return String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '');
  };
  const headers = rows[0].map(norm);
  const index = function (names) { return headers.findIndex(function (header) { return names.indexOf(header) >= 0; }); };
  const dateIndex = index(['date', 'fecha', 'period', 'periodo']);
  const valueIndex = index(['value', 'valor', 'observation', 'observacion']);
  if (dateIndex < 0 || valueIndex < 0) throw new Error(fileName + ' needs fecha/date and valor/value columns.');

  const metadata = function (names) {
    const ix = index(names);
    if (ix < 0) return '';
    for (let i = 1; i < rows.length; i++) {
      const value = String(rows[i][ix] || '').trim();
      if (value) return value;
    }
    return '';
  };
  const observations = [];
  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    if (!String(row[dateIndex] || '').trim() && !String(row[valueIndex] || '').trim()) continue;
    const date = normalizeDate_(row[dateIndex]);
    const value = parseNumber_(row[valueIndex], delimiter);
    if (!date || value === null) throw new Error(fileName + ' has an invalid date or value on row ' + (i + 1) + '.');
    observations.push({ date: date, value: value });
  }
  if (!observations.length) throw new Error(fileName + ' contains no usable observations.');
  observations.sort(function (a, b) { return a.date.localeCompare(b.date); });

  const stem = fileName.replace(/\.csv$/i, '');
  const id = slug_(metadata(['id', 'seriesid', 'serieid']) || stem);
  const label = metadata(['label', 'etiqueta', 'seriesname', 'nombre']) || stem.replace(/[_-]+/g, ' ');
  const unit = metadata(['unit', 'unidad']) || 'valor';
  const frequency = (metadata(['freq', 'frequency', 'frecuencia', 'periodicity', 'periodicidad']) || inferFrequency_(observations)).toUpperCase();
  if (['D', 'M', 'Q'].indexOf(frequency) < 0) throw new Error(fileName + ' frequency must be D, M, or Q.');
  const allowedBlocks = ['actividad', 'coyuntura', 'empleo', 'precios', 'vivienda', 'publico', 'exterior', 'financiero', 'credito', 'manual'];
  const requestedBlock = metadata(['block', 'bloque']).toLowerCase();
  const block = allowedBlocks.indexOf(requestedBlock) >= 0 ? requestedBlock : 'manual';
  return { id: id, label: label, unit: unit, freq: frequency, block: block };
}

function normalizeDate_(value) {
  const s = String(value || '').trim();
  let m;
  if ((m = s.match(/^(\d{4})[-/](\d{1,2})(?:[-/](\d{1,2}))?$/))) {
    const year = Number(m[1]), month = Number(m[2]), day = Number(m[3] || 1);
    if (month < 1 || month > 12 || day < 1 || day > 31) return '';
    return m[1] + '-' + ('0' + month).slice(-2) + '-' + ('0' + day).slice(-2);
  }
  if ((m = s.match(/^(\d{4})\s*[- ]?[QqTt]([1-4])$/))) {
    const month = (Number(m[2]) - 1) * 3 + 1;
    return m[1] + '-' + ('0' + month).slice(-2) + '-01';
  }
  if ((m = s.match(/^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$/))) {
    const day = Number(m[1]), month = Number(m[2]);
    if (month < 1 || month > 12 || day < 1 || day > 31) return '';
    return m[3] + '-' + ('0' + month).slice(-2) + '-' + ('0' + day).slice(-2);
  }
  return '';
}

function parseNumber_(value, delimiter) {
  let text = String(value || '').trim().replace(/[\s\u00a0]/g, '');
  if (!text) return null;
  if (delimiter === ';' && text.indexOf(',') >= 0) text = text.replace(/\./g, '').replace(',', '.');
  else if (text.indexOf(',') >= 0 && text.indexOf('.') >= 0) text = text.replace(/,/g, '');
  else if (text.indexOf(',') >= 0) text = text.replace(',', '.');
  const number = Number(text);
  return isFinite(number) ? number : null;
}

function inferFrequency_(observations) {
  if (observations.length < 2) return 'M';
  const gaps = [];
  for (let i = 1; i < observations.length; i++) {
    gaps.push((new Date(observations[i].date) - new Date(observations[i - 1].date)) / 86400000);
  }
  gaps.sort(function (a, b) { return a - b; });
  const median = gaps[Math.floor(gaps.length / 2)];
  return median <= 7 ? 'D' : median <= 45 ? 'M' : 'Q';
}

function slug_(value) {
  const slug = String(value).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9_-]+/g, '_').replace(/^[_-]+|[_-]+$/g, '').slice(0, 60);
  if (!slug) throw new Error('CSV filename or id must produce a valid series ID.');
  return slug;
}

function putGithubFile_(path, text, message, token) {
  const existing = getGithubFile_(path, token);
  if (existing && existing.text === text) return false;
  const payload = {
    message: message,
    content: Utilities.base64Encode(Utilities.newBlob(text, 'text/plain').getBytes()),
    branch: CONFIG.branch
  };
  if (existing) payload.sha = existing.sha;
  const response = UrlFetchApp.fetch(githubContentsUrl_(path), {
    method: 'put', contentType: 'application/json',
    headers: githubHeaders_(token), payload: JSON.stringify(payload), muteHttpExceptions: true
  });
  const status = response.getResponseCode();
  if (status < 200 || status >= 300) throw new Error('GitHub could not update ' + path + ' (HTTP ' + status + '): ' + response.getContentText().slice(0, 300));
  return true;
}

function putGithubBytes_(path, bytes, message, token) {
  const existing = getGithubFile_(path, token);
  const payload = {
    message: message,
    content: Utilities.base64Encode(bytes),
    branch: CONFIG.branch
  };
  if (existing) payload.sha = existing.sha;
  const response = UrlFetchApp.fetch(githubContentsUrl_(path), {
    method: 'put', contentType: 'application/json',
    headers: githubHeaders_(token), payload: JSON.stringify(payload), muteHttpExceptions: true
  });
  const status = response.getResponseCode();
  if (status < 200 || status >= 300) throw new Error('GitHub could not update ' + path + ' (HTTP ' + status + '): ' + response.getContentText().slice(0, 300));
  return true;
}

function getGithubFile_(path, token) {
  const response = UrlFetchApp.fetch(githubContentsUrl_(path) + '?ref=' + encodeURIComponent(CONFIG.branch), {
    method: 'get', headers: githubHeaders_(token), muteHttpExceptions: true
  });
  const status = response.getResponseCode();
  if (status === 404) return null;
  if (status < 200 || status >= 300) throw new Error('GitHub could not read ' + path + ' (HTTP ' + status + ').');
  const result = JSON.parse(response.getContentText());
  const encoded = String(result.content || '').replace(/\s/g, '');
  const text = encoded ? Utilities.newBlob(Utilities.base64Decode(encoded)).getDataAsString('UTF-8') : '';
  return { sha: result.sha, text: text };
}

function githubContentsUrl_(path) {
  const encodedPath = path.split('/').map(encodeURIComponent).join('/');
  return 'https://api.github.com/repos/' + CONFIG.owner + '/' + CONFIG.repo + '/contents/' + encodedPath;
}

function githubHeaders_(token) {
  return {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };
}

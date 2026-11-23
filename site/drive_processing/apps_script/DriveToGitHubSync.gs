/**
 * Sync Big Data, Manual and optional Turkey data to drive_processing.
 * Store the GitHub credential only in Apps Script Project Properties.
 * Required property: GITHUB_TOKEN
 * Optional property: DRIVE_TURKEY_FOLDER_ID (configure when that folder exists)
 */
const CONFIG = {
  owner: 'marcos-laserna',
  repo: 'fow_dashboard',
  branch: 'main',
  bigDataFolderId: '1thGWH7iyzwmC3YDjMHf1J_vwmPfNpm8H',
  manualFolderId: '1U8giN5bJ4tJLAtVf_rjlxLu9s6qGr3u2',
  manualSpreadsheetId: '1lqU0EbQHoDATmfNNOl7yodFTve6MYxCHLjCoRczsVy8',
  bigDataRepoFolder: 'site/drive_processing/drive_data/bigdata',
  manualRepoFolder: 'site/drive_processing/manual_csv',
  manualWorkbookFolder: 'site/drive_processing/drive_data/manual',
  turkeyRepoFolder: 'site/drive_processing/turkey_csv',
  turkeyFolderProperty: 'DRIVE_TURKEY_FOLDER_ID',
  bigDataCsvNames: ['Tabla_monitor.csv', 'Datos_informe.csv']
};

function syncDriveToGitHub() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const props = PropertiesService.getScriptProperties();
    const token = props.getProperty('GITHUB_TOKEN');
    if (!token) throw new Error('Set GITHUB_TOKEN in Apps Script Project Properties.');
    const pending = newBatch_();
    const errors = [];
    const sources = {
      'Big Data': batch => syncBigDataFolder_(props, batch),
      'Manual workbook': batch => syncManualWorkbook_(props, batch),
      'Manual CSV': batch => syncSeriesFolder_(DriveApp.getFolderById(CONFIG.manualFolderId), 'manual', props, batch),
    };
    const turkeyFolderId = props.getProperty(CONFIG.turkeyFolderProperty);
    if (turkeyFolderId) {
      sources['Turkey CSV'] = batch => syncSeriesFolder_(DriveApp.getFolderById(turkeyFolderId), 'turkey', props, batch);
    }
    Object.keys(sources).forEach(function (label) {
      const batch = newBatch_();
      try {
        sources[label](batch);
        pending.entries.push(...batch.entries);
        Object.assign(pending.properties, batch.properties);
      } catch (error) {
        errors.push(label + ': ' + error.message);
      }
    });
    const sha = commitGithubBatch_(pending.entries, token);
    if (Object.keys(pending.properties).length) props.setProperties(pending.properties);
    Logger.log(sha ? 'GitHub sync commit: ' + sha : 'GitHub sync: no changes.');
    if (errors.length) throw new Error(errors.join('\n'));
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

function syncBigDataFolder_(props, batch) {
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
    const sha256 = stageText_(batch, props, path, csv);
    const updated = file.getLastUpdated();
    if (!latest || updated.getTime() > latest.getTime()) latest = updated;
    manifestFiles.push({ file: name, updated_at: updated.toISOString(), size: file.getSize(), sha256 });
  });
  const manifest = { version: 1, updated_at: latest ? latest.toISOString() : null, files: manifestFiles };
  stageManifest_(batch, props, CONFIG.bigDataRepoFolder, manifest);
}

function syncManualWorkbook_(props, batch) {
  const folder = DriveApp.getFolderById(CONFIG.manualFolderId);
  const candidates = [];
  const iterator = folder.getFiles();
  while (iterator.hasNext()) {
    const file = iterator.next();
    if (file.getId() === CONFIG.manualSpreadsheetId &&
        file.getMimeType() === 'application/vnd.google-apps.spreadsheet') candidates.push(file);
  }
  if (!candidates.length) throw new Error('Could not find the configured Alta Frecuencia Google Sheet in its Drive folder.');
  const file = candidates[0];
  const updated = file.getLastUpdated();
  const modifiedProperty = 'MANUAL_WORKBOOK_MODIFIED_' + file.getId();
  const sizeProperty = 'MANUAL_WORKBOOK_SIZE_' + file.getId();
  const path = CONFIG.manualWorkbookFolder + '/alta_frecuencia.xlsx';
  let sha256 = props.getProperty(digestProperty_(path));
  let size = Number(props.getProperty(sizeProperty) || 0);
  if (!sha256 || props.getProperty(modifiedProperty) !== String(updated.getTime())) {
    const bytes = exportSpreadsheetXlsx_(file.getId());
    sha256 = stageChange_(batch, props, path, bytes, { bytes });
    size = bytes.length;
    batch.properties[sizeProperty] = String(size);
    batch.properties[modifiedProperty] = String(updated.getTime());
  }
  const manifest = {
    version: 1,
    updated_at: updated.toISOString(),
    files: [{ file: 'alta_frecuencia.xlsx', source_title: file.getName(), source_updated_at: updated.toISOString(), size, sha256 }]
  };
  stageManifest_(batch, props, CONFIG.manualWorkbookFolder, manifest);
}

function syncSeriesFolder_(folder, collection, props, batch) {
  const turkey = collection === 'turkey';
  const prefix = turkey ? 'turquia_' : 'manual_';
  const destination = turkey ? CONFIG.turkeyRepoFolder : CONFIG.manualRepoFolder;
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
    const suffix = parsed.id.startsWith(prefix) ? parsed.id.slice(prefix.length) : parsed.id;
    const id = (prefix + suffix).slice(0, 60);
    if (seenIds[id]) throw new Error('Two CSV files produce the same series ID: ' + id);
    seenIds[id] = true;
    const githubName = id + '.csv';
    const sha256 = stageText_(batch, props, destination + '/' + githubName, csv);
    const updated = file.getLastUpdated();
    if (!latest || updated.getTime() > latest.getTime()) latest = updated;
    manifestFiles.push({ id: id, file: githubName, label: parsed.label, unit: parsed.unit, freq: parsed.freq,
      block: collection, source: turkey ? 'Google Drive · Turquía CSV' : 'Google Drive · CSV', updated_at: updated.toISOString(), sha256 });
  }
  manifestFiles.sort(function (a, b) { return a.id.localeCompare(b.id); });
  const manifest = { version: 1, updated_at: latest ? latest.toISOString() : null, files: manifestFiles };
  stageManifest_(batch, props, destination, manifest);
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

function newBatch_() {
  return { entries: [], properties: {} };
}

function stageManifest_(batch, props, folder, manifest) {
  stageText_(batch, props, folder + '/manifest.json', JSON.stringify(manifest, null, 2) + '\n');
}

function stageText_(batch, props, path, content) {
  const bytes = Utilities.newBlob(content, 'text/plain').getBytes();
  return stageChange_(batch, props, path, bytes, bytes.length > 1000000 ? { bytes } : { content });
}

function digestProperty_(path) {
  return 'DRIVE_BATCH_SHA256_' + path;
}

function stageChange_(batch, props, path, bytes, value) {
  const digest = sha256Hex_(bytes);
  const property = digestProperty_(path);
  if (props.getProperty(property) !== digest) {
    batch.entries.push(Object.assign({ path }, value));
    batch.properties[property] = digest;
  }
  return digest;
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

function commitGithubBatch_(entries, token) {
  if (!entries.length) return null;
  const tree = entries.map(function (file) {
    const entry = {path: file.path, mode: '100644', type: 'blob'};
    if (file.bytes) {
      entry.sha = githubJson_('/git/blobs', 'post', {
        content: Utilities.base64Encode(file.bytes), encoding: 'base64'
      }, token).sha;
    } else {
      entry.content = file.content;
    }
    return entry;
  });

  const ref = '/heads/' + encodeURIComponent(CONFIG.branch);
  const readHead = () => githubJson_('/git/ref' + ref, 'get', null, token).object.sha;
  for (let attempt = 1; attempt <= 3; attempt++) {
    const head = readHead();
    const baseTree = githubJson_('/git/commits/' + head, 'get', null, token).tree.sha;
    const nextTree = githubJson_('/git/trees', 'post', {base_tree: baseTree, tree: tree}, token).sha;
    if (nextTree === baseTree) return null;
    const commit = githubJson_('/git/commits', 'post', {
      message: 'Sync dashboard sources from Drive', tree: nextTree, parents: [head]
    }, token);
    try {
      githubJson_('/git/refs' + ref, 'patch', {sha: commit.sha, force: false}, token);
      return commit.sha;
    } catch (error) {
      // Only retry if a concurrent update moved the branch.
      if (![409, 422].includes(error.status) || attempt === 3 ||
          readHead() === head) throw error;
      Utilities.sleep(300 * attempt);
    }
  }
}

function githubJson_(endpoint, method, payload, token) {
  const options = {method: method, headers: githubHeaders_(token), muteHttpExceptions: true};
  if (payload !== null) {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(payload);
  }
  const response = UrlFetchApp.fetch(
    'https://api.github.com/repos/' + CONFIG.owner + '/' + CONFIG.repo + endpoint, options
  );
  const status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    const error = new Error('GitHub ' + method + ' ' + endpoint + ' (HTTP ' + status + '): ' +
      response.getContentText().slice(0, 300));
    error.status = status;
    throw error;
  }
  return JSON.parse(response.getContentText());
}

function githubHeaders_(token) {
  return {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };
}

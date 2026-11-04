#!/usr/bin/env python3
"""Языки для переводчика Klira: берёт свежие модели Mozilla (MPL-2.0) и кладёт их в релиз translator-models.

Что делает за один запуск:
  1. Читает публичный список моделей Mozilla (Remote Settings, translations-models).
  2. Для каждой пары «язык <-> английский» выбирает самую свежую стабильную версию (без alpha).
  3. Если такой версии ещё нет в downloads/models.json или её файла нет в релизе, скачивает три файла
     (модель, словарь подсказок, словарь слов), проверяет контрольную сумму Mozilla и собирает один zip.
  4. Загружает zip в релиз translator-models, считает SHA-256 уже нашего zip и записывает всё в downloads/models.json.
Klira читает только models.json и скачивает только те zip, которые нужны пользователю, проверяя SHA-256.
Старые версии файлов в релизе остаются, поэтому старые копии Klira продолжают работать.

Переменные: GH_TOKEN, REPO (владелец/репозиторий), ONLY (необязательно: коды языков через запятую для пробного запуска).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import zipfile

REG = 'https://firefox.settings.services.mozilla.com/v1'
RELEASE = 'translator-models'
MANIFEST = 'downloads/models.json'
REPO = os.environ.get('REPO', 'VizitSpace/klira')
ONLY = [x.strip() for x in os.environ.get('ONLY', '').split(',') if x.strip()]
WORK = 'work'


def log(*a):
    print(*a, flush=True)


def http_get(url, dest=None, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'klira-models-build'})
            with urllib.request.urlopen(req, timeout=120) as r:
                if dest is None:
                    return r.read()
                h = hashlib.sha256()
                with open(dest, 'wb') as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        h.update(chunk)
                return h.hexdigest()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError('download failed: %s (%s)' % (url, last))


def vkey(v):
    return tuple(int(x) for x in v.split('.'))


def stable(v):
    return re.fullmatch(r'\d+(\.\d+)*', v or '') is not None


def sh(*args, check=True):
    return subprocess.run(args, check=check, capture_output=True, text=True)


def unpack_if_needed(path):
    """Файлы Mozilla лежат как есть; на случай сжатия (gzip или zstd) распаковываем."""
    with open(path, 'rb') as f:
        magic = f.read(4)
    if magic[:2] == b'\x1f\x8b':
        import gzip
        out = path + '.raw'
        with gzip.open(path, 'rb') as a, open(out, 'wb') as b:
            while True:
                chunk = a.read(1 << 20)
                if not chunk:
                    break
                b.write(chunk)
        os.replace(out, path)
        log('  gzip unpacked')
    elif magic == b'\x28\xb5\x2f\xfd':
        import zstandard
        out = path + '.raw'
        with open(path, 'rb') as a, open(out, 'wb') as b:
            zstandard.ZstdDecompressor().copy_stream(a, b)
        os.replace(out, path)
        log('  zstd unpacked')


def main():
    os.makedirs(WORK, exist_ok=True)
    base = json.loads(http_get(REG + '/').decode())['capabilities']['attachments']['base_url']
    recs = json.loads(http_get(REG + '/buckets/main/collections/translations-models/records?_limit=5000').decode())['data']
    log('records:', len(recs))

    # (from, to) -> version -> fileType -> record
    pairs = {}
    for r in recs:
        f, t, ft, v = r.get('fromLang'), r.get('toLang'), r.get('fileType'), r.get('version')
        if not (f and t and ft and v) or not stable(v):
            continue
        if f != 'en' and t != 'en':
            continue
        if ONLY and not ({f, t} - {'en'}) & set(ONLY):
            continue
        pairs.setdefault((f, t), {}).setdefault(v, {})[ft] = r

    chosen = {}
    for key, versions in sorted(pairs.items()):
        for v in sorted(versions, key=vkey, reverse=True):
            fts = versions[v]
            if 'model' in fts and 'lex' in fts and ('vocab' in fts or ('srcvocab' in fts and 'trgvocab' in fts)):
                chosen[key] = (v, fts)
                break
        else:
            log('skip (no complete stable version):', key)
    log('pairs to consider:', len(chosen))

    old = {}
    if os.path.exists(MANIFEST):
        try:
            old = {(m['from'], m['to']): m for m in json.load(open(MANIFEST, encoding='utf-8')).get('models', [])}
        except Exception as e:  # noqa: BLE001
            log('old manifest unreadable:', e)

    # release must exist
    if sh('gh', 'release', 'view', RELEASE, '-R', REPO, check=False).returncode != 0:
        sh('gh', 'release', 'create', RELEASE, '-R', REPO, '--latest=false',
           '--title', 'Языки для переводчика Klira',
           '--notes', 'Файлы языков для встроенного переводчика Klira: модели Mozilla Firefox Translations (MPL-2.0). '
                      'Сюда они попадают автоматически, вручную скачивать ничего не нужно: Klira сама берёт нужные из downloads/models.json.')
    rid = sh('gh', 'api', 'repos/%s/releases/tags/%s' % (REPO, RELEASE), '--jq', '.id').stdout.strip()
    have = set(sh('gh', 'api', '--paginate', 'repos/%s/releases/%s/assets?per_page=100' % (REPO, rid), '--jq', '.[].name').stdout.split())
    log('assets already in release:', len(have))

    models = {k: v for k, v in old.items()}
    failed = []
    for (f, t), (ver, fts) in sorted(chosen.items()):
        fname = '%s-%s-v%s.zip' % (f, t, ver)
        cur = old.get((f, t))
        if cur and cur.get('version') == ver and cur.get('file') in have:
            continue
        if cur and vkey(cur['version']) > vkey(ver) and cur.get('file') in have:
            continue
        log('==', fname)
        try:
            names = {'model': 'model.bin', 'lex': 'lex.bin', 'vocab': 'vocab.spm', 'srcvocab': 'srcvocab.spm', 'trgvocab': 'trgvocab.spm'}
            tmp = []
            for ft, rec in fts.items():
                if ft not in names:
                    continue
                att = rec['attachment']
                p = os.path.join(WORK, '%s-%s-%s' % (f, t, ft))
                got = http_get(base + att['location'], p)
                if got != att['hash']:
                    raise RuntimeError('hash mismatch for %s: %s != %s' % (ft, got, att['hash']))
                unpack_if_needed(p)
                tmp.append((names[ft], p))
            meta = {'from': f, 'to': t, 'version': ver, 'source': 'Mozilla Firefox Translations models',
                    'license': 'MPL-2.0', 'architecture': fts['model'].get('architecture', ''),
                    'files': {n: fts[k].get('name', '') for k, n in names.items() if k in fts}}
            zpath = os.path.join(WORK, fname)
            with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for n, p in tmp:
                    z.write(p, n)
                z.writestr('meta.json', json.dumps(meta, ensure_ascii=False, indent=1))
            h = hashlib.sha256()
            with open(zpath, 'rb') as zf:
                for chunk in iter(lambda: zf.read(1 << 20), b''):
                    h.update(chunk)
            size = os.path.getsize(zpath)
            sh('gh', 'release', 'upload', RELEASE, zpath, '-R', REPO, '--clobber')
            models[(f, t)] = {'from': f, 'to': t, 'version': ver, 'file': fname, 'size': size, 'sha256': h.hexdigest()}
            log('  ok', size)
            for _, p in tmp:
                os.remove(p)
            os.remove(zpath)
        except Exception as e:  # noqa: BLE001
            log('  FAILED:', e)
            failed.append(fname)
        write_manifest(models)

    write_manifest(models)
    log('done, models in manifest:', len(models), 'failed:', failed)
    if failed:
        sys.exit(1)


def write_manifest(models):
    os.makedirs('downloads', exist_ok=True)
    data = {
        'schema': 1,
        'updated': time.strftime('%Y-%m-%d', time.gmtime()),
        'url': 'https://github.com/%s/releases/download/%s/' % (REPO, RELEASE),
        'license': 'Mozilla Firefox Translations models, MPL-2.0',
        'models': sorted(models.values(), key=lambda m: (m['from'], m['to'])),
    }
    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')


if __name__ == '__main__':
    main()

"""Bounded, read-only verification of an immutable snapshot and its base chain."""
import csv
import time
from datetime import datetime,timezone

MAX_FILES=100
MAX_BYTES=32*1024*1024
MAX_ROW_WORK=250000
MAX_SECONDS=5


class BudgetReached(Exception):pass


def inspect_history(store,logger,snapshot,*,max_files=MAX_FILES,max_bytes=MAX_BYTES,max_row_work=MAX_ROW_WORK,max_seconds=MAX_SECONDS):
    # Validate API identifiers before converting archive failures to report entries.
    store._folder(logger,snapshot)
    started=time.monotonic();deadline=started+max_seconds
    result={'scope':'selected_history_chain','logger':logger,'snapshot':snapshot,'checked_at':datetime.now(timezone.utc).isoformat(),
            'state':'partial','complete':False,'clock_verified':False,'snapshots_checked':0,'files_checked':0,'rows_checked':0,
            'bytes_planned':0,'row_work_planned':0,'reason':None,
            'limits':{'files':max_files,'bytes':max_bytes,'row_work':max_row_work,'seconds':max_seconds}}
    if not store.lock.acquire(blocking=False):
        result.update(reason='Historienablage ist belegt; später erneut prüfen.',elapsed_seconds=0);return result
    try:
        current=snapshot;seen=set();chain=[];files=0
        def preflight(path):
            nonlocal files
            if time.monotonic()>=deadline:raise BudgetReached('Zeitbudget erreicht; kein vollständiger Nachweis.')
            relative=path.relative_to(store.root)
            if store.root.is_symlink() or any((store.root.joinpath(*relative.parts[:i])).is_symlink() for i in range(1,len(relative.parts)+1)):
                raise ValueError('Symbolischer Archivpfad.')
            if not path.is_file():raise ValueError('Archivdatei fehlt oder ist keine reguläre Datei.')
            files+=1;size=path.stat().st_size
            if files>max_files or result['bytes_planned']+size>max_bytes:raise BudgetReached('Datei-/Byte-Limit erreicht; Zeitraumstand nicht vollständig geprüft.')
            result['bytes_planned']+=size
            return size
        while True:
            if current in seen or len(chain)>=32:raise ValueError('Ungültige Historienkette.')
            seen.add(current);folder=store._folder(logger,current)
            if preflight(folder/'manifest.json')>256*1024:raise BudgetReached('Manifest zu groß für diese Diagnose.')
            meta=store.metadata(logger,current)
            if type(meta.get('count')) is not int or meta['count']<=0:raise ValueError('Ungültiger Historienumfang.')
            result['row_work_planned']+=meta['count']
            if result['row_work_planned']>max_row_work:raise BudgetReached('Zeilen-Prüfaufwand erreicht; kein vollständiger Nachweis.')
            chain.append(meta)
            for name in meta['files']:preflight(folder/name)
            if meta.get('storage','full')!='delta':break
            current=meta['base_snapshot']
        for child,base in zip(chain,chain[1:]):
            if child['delta_depth']!=base.get('delta_depth',0)+1:raise ValueError('Widersprüchliche Kettentiefe.')
        if chain[-1].get('delta_depth',0)!=0:raise ValueError('Ungültige Vollbestandsbasis.')
        if time.monotonic()>=deadline:raise BudgetReached('Zeitbudget vor Inhaltsprüfung erreicht.')
        # Reuse the archive's checksum, sequence, count and content-ID verifier.
        rows=store.rows(logger,snapshot)
        result.update(snapshots_checked=len(chain),files_checked=files,rows_checked=len(rows))
        if time.monotonic()>deadline:raise BudgetReached('Inhalt geprüft, Zeitbudget überschritten; kein fristgerechter Gesamtnachweis.')
        result.update(state='ok',complete=True,reason='Prüfsummen, Sequenzen, Umfänge und Inhaltskennungen der Kette ohne Befund. Gerätezeit bleibt ungeprüft.')
    except BudgetReached as exc:result['reason']=str(exc)
    except (OSError,ValueError,TypeError,KeyError,OverflowError,UnicodeError,csv.Error,RecursionError):
        result.update(state='error',reason='Archivdateien, Metadaten, Prüfsummen oder Historienkette fehlerhaft. Originale unverändert; keine Reparatur.')
    finally:store.lock.release()
    result['elapsed_seconds']=round(time.monotonic()-started,3)
    return result

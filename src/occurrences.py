"""Small, bounded GBIF search and aggregated teaching plots."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API = 'https://api.gbif.org/v1'

def get_json(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent':'OLC-GBIF-teaching/1.0'}), timeout=45) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except URLError:
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)

def match_name(name):
    result = get_json(API+'/species/match?'+urlencode({'name':name,'strict':'true'}))
    if result.get('matchType') != 'EXACT' or result.get('rank') != 'SPECIES':
        raise ValueError(f'Name requires review: {name}; {result.get("matchType")} / {result.get("rank")}')
    key = result.get('acceptedUsageKey', result.get('usageKey'))
    accepted = get_json(f'{API}/species/{key}')
    return dict(queried_name=name, matched_name=result['scientificName'], matched_key=result['usageKey'],
                accepted_name=accepted['scientificName'], accepted_key=key, match_type=result['matchType'],
                matched_status=result['status'], checked_utc=datetime.now(timezone.utc).isoformat(),
                taxonomy='GBIF Backbone Taxonomy via v1 species/match', raw_match=result)

def query_parameters(key, bbox, years):
    west,south,east,north = bbox
    if not all(math.isfinite(x) for x in bbox) or not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError('Use a valid west, south, east, north bounding box.')
    first,last = years
    if not 1 <= first <= last <= datetime.now().year:
        raise ValueError('Use ordered historical years.')
    # Exterior ring is counter-clockwise; coordinates are longitude, latitude.
    geometry=f'POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))'
    return dict(taxonKey=key, geometry=geometry, hasCoordinate='true', hasGeospatialIssue='false',
                occurrenceStatus='PRESENT', year=f'{first},{last}')

def search_records(params, maximum=3000, fetch=get_json):
    if not 1 <= maximum <= 100000:
        raise ValueError('Search cap must be 1–100000; use a GBIF download for larger results.')
    records=[]
    pages=[]
    offset=0
    while True:
        url=API+'/occurrence/search?'+urlencode(dict(params,limit=min(300,maximum-offset),offset=offset))
        page=fetch(url)
        if int(page['count']) > maximum:
            raise ValueError(f"Query matches {page['count']} records, above the {maximum} cap. Narrow filters or use a DOI-bearing GBIF download; no partial plot produced.")
        batch=page['results']
        pages.append(dict(url=url,reported_count=page['count'],returned=len(batch)))
        records.extend(batch)
        offset+=len(batch)
        if page.get('endOfRecords'):
            break
        if not batch or offset >= maximum:
            raise ValueError('Pagination incomplete; retry or use the bulk download workflow.')
    unique={r['key']:r for r in records}
    return list(unique.values()), pages, len(records)-len(unique)

def retrieve(name, bbox, years, data_dir, refresh=False):
    data_dir=Path(data_dir)
    spec=dict(name=name,bbox=list(bbox),years=list(years),query_version=1)
    tag=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()[:12]
    cached=data_dir/f'{tag}.json'
    if cached.exists() and not refresh:
        payload=json.loads(cached.read_text(encoding='utf-8'))
        if payload['selection'] != spec:
            raise ValueError('Cache selection mismatch.')
        return payload
    match=match_name(name)
    params=query_parameters(match['accepted_key'],bbox,years)
    records,pages,duplicates=search_records(params)
    payload=dict(selection=spec,taxon=match,query=params,records=records,pages=pages,
                 duplicate_keys_removed=duplicates,retrieved_utc=datetime.now(timezone.utc).isoformat(),
                 search_snapshot=True,download_doi=None)
    payload['records_sha256']=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest()
    data_dir.mkdir(parents=True,exist_ok=True)
    if refresh and cached.exists():
        cached=cached.with_name(f'{tag}-{time.time_ns()}.json')
    cached.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    return payload

def summarize(payload):
    import pandas as pd
    records=payload['records']
    columns=['key','decimalLongitude','decimalLatitude','year','eventDate','basisOfRecord',
             'coordinateUncertaintyInMeters','datasetKey','license','occurrenceID','issues','references']
    frame=pd.DataFrame(records).reindex(columns=columns)
    for name in ['decimalLongitude','decimalLatitude','year','coordinateUncertaintyInMeters']:
        frame[name]=pd.to_numeric(frame[name],errors='coerce')
    west,south,east,north=payload['selection']['bbox']
    good=frame.decimalLongitude.between(west,east) & frame.decimalLatitude.between(south,north)
    good &= ~frame.basisOfRecord.isin(['FOSSIL_SPECIMEN','LIVING_SPECIMEN'])
    good &= frame.year.between(*payload['selection']['years'])
    clean=frame.loc[good].copy()
    summary=dict(retrieved_records=len(frame),mapped_records=len(clean),excluded_locally=int((~good).sum()),
        duplicate_keys_removed=payload['duplicate_keys_removed'],
        missing_event_date=int(frame.eventDate.isna().sum()),missing_year=int(frame.year.isna().sum()),
        missing_coordinate_uncertainty=int(frame.coordinateUncertaintyInMeters.isna().sum()),
        uncertainty_above_10km=int((frame.coordinateUncertaintyInMeters>10000).sum()),
        earliest_year=int(clean.year.min()) if len(clean) else None,
        latest_year=int(clean.year.max()) if len(clean) else None,
        record_types=frame.basisOfRecord.fillna('UNSPECIFIED').value_counts().to_dict())
    return clean,summary

def draw_summary(payload, output):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    import numpy as np
    clean,quality=summarize(payload)
    west,south,east,north=payload['selection']['bbox']
    fig,(ax,bar)=plt.subplots(1,2,figsize=(12,5),gridspec_kw={'width_ratios':[1.25,1]})
    fig.patch.set_facecolor('#faf8f1')
    for panel in (ax,bar): panel.set_facecolor('#faf8f1')
    xedges=np.linspace(west,east,max(1,math.ceil((east-west)/0.2))+1)
    yedges=np.linspace(south,north,max(1,math.ceil((north-south)/0.2))+1)
    counts,_,_=np.histogram2d(clean.decimalLongitude,clean.decimalLatitude,bins=[xedges,yedges])
    visible=np.ma.masked_where(counts.T < 3,counts.T)
    if visible.count():
        mesh=ax.pcolormesh(xedges,yedges,visible,cmap='YlGnBu',vmin=3)
        fig.colorbar(mesh,ax=ax,shrink=.7,label='Occurrence records per cell')
    else:
        ax.text(.5,.5,'No cells with at least 3 records',ha='center',transform=ax.transAxes)
    ax.add_patch(Rectangle((west,south),east-west,north-south,fill=False,edgecolor='#405b4b',lw=2,linestyle='--'))
    ax.set(xlim=(west-.03,east+.03),ylim=(south-.03,north+.03),xlabel='Longitude',ylabel='Latitude',title='Regional search box · aggregated records')
    ax.set_aspect(1/math.cos(math.radians((south+north)/2)))
    if len(clean):
        first,last=payload['selection']['years']
        decades=list(range(first//10*10,last//10*10+1,10))
        tally=(clean.year.astype(int)//10*10).value_counts().reindex(decades,fill_value=0)
        bar.bar(tally.index,tally.values,width=7,color='#32756b')
    else: bar.text(.5,.5,'No matching records',ha='center',transform=bar.transAxes)
    bar.set(xlabel='Observation decade',ylabel='Occurrence records',title='Record history · not a population trend')
    bar.spines[['top','right']].set_visible(False)
    title=payload['taxon']['queried_name']
    fig.suptitle(f'{title} | Pine Ridge regional example',fontsize=17,fontweight='bold',color='#233d35')
    fig.text(.03,.02,f"GBIF search snapshot {payload['retrieved_utc'][:10]} · {quality['mapped_records']} retained records\nApprox. 0.2° cells; cells below 3 records hidden. Dashed outline is a search box, not a reservation boundary.",fontsize=9,color='#44504a')
    fig.tight_layout(rect=(0,.11,1,.91))
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=160,facecolor=fig.get_facecolor())
    return fig,quality

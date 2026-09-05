import sys
from pathlib import Path
import unittest
from urllib.parse import parse_qs,urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from occurrences import search_records,query_parameters,summarize

class OccurrenceTests(unittest.TestCase):
    def test_pagination(self):
        offsets=[]
        def fetch(url):
            q=parse_qs(urlparse(url).query);offset=int(q['offset'][0]);offsets.append(offset)
            self.assertLessEqual(int(q['limit'][0]),300)
            return dict(count=301,results=[dict(key=n) for n in range(offset,min(301,offset+300))],endOfRecords=offset==300)
        rows,pages,duplicates=search_records({},fetch=fetch)
        self.assertEqual((len(rows),offsets,duplicates),(301,[0,300],0))

    def test_cap_stops_before_partial_result(self):
        with self.assertRaises(ValueError):
            search_records({},maximum=10,fetch=lambda url:dict(count=11,results=[],endOfRecords=False))

    def test_empty_and_duplicates(self):
        rows,_,_=search_records({},fetch=lambda url:dict(count=0,results=[],endOfRecords=True))
        self.assertEqual(rows,[])
        rows,_,duplicates=search_records({},fetch=lambda url:dict(count=2,results=[dict(key=1),dict(key=1)],endOfRecords=True))
        self.assertEqual((len(rows),duplicates),(1,1))

    def test_polygon_and_invalid_bounds(self):
        params=query_parameters(1,(-103,42,-102,43),(1900,2025))
        self.assertEqual(params['geometry'],'POLYGON((-103 42,-102 42,-102 43,-103 43,-103 42))')
        with self.assertRaises(ValueError): query_parameters(1,(-102,42,-103,43),(1900,2025))

    def test_quality_exclusions_and_empty(self):
        base=dict(key=1,decimalLongitude=-102,decimalLatitude=43,year=2000,basisOfRecord='PRESERVED_SPECIMEN')
        payload=dict(selection=dict(bbox=[-103,42,-101,44],years=[1900,2025]),duplicate_keys_removed=0,
                     records=[base,dict(base,key=2,basisOfRecord='FOSSIL_SPECIMEN'),dict(base,key=3,decimalLongitude=0)])
        clean,quality=summarize(payload)
        self.assertEqual((len(clean),quality['excluded_locally']),(1,2))
        payload['records']=[]
        self.assertEqual(summarize(payload)[1]['mapped_records'],0)

if __name__=='__main__': unittest.main()

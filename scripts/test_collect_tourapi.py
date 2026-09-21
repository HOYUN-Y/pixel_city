import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import collect_tourapi as tour


class CollectionTests(unittest.TestCase):
    def test_empty_and_single_item(self):
        self.assertEqual(tour.unpack({'response': {'header': {'resultCode': '0000'}, 'body': {'items': ''}}})[2], [])
        data = {'response': {'header': {'resultCode': '0000'}, 'body': {'items': {'item': {'contentid': '1'}}}}}
        self.assertEqual(tour.unpack(data)[2], [{'contentid': '1'}])

    def test_gateway_error(self):
        self.assertEqual(tour.unpack({'OpenAPI_ServiceResponse': {'cmmMsgHeader': {'returnReasonCode': '30'}}})[0], '30')
        self.assertEqual(tour.unpack({'resultCode': '10', 'resultMsg': 'INVALID_REQUEST_PARAMETER_ERROR'})[0], '10')

    def test_coordinates(self):
        for item in ({}, {'mapx': 0, 'mapy': 0}, {'mapx': 'nan', 'mapy': 37.57}):
            self.assertIsNone(tour.coordinates(item))
            self.assertFalse(tour.inside(item))
        self.assertTrue(tour.inside({'mapx': '126.977', 'mapy': '37.575'}))
        self.assertFalse(tour.inside({'mapx': '127', 'mapy': '37.575'}))

    def test_keyword_candidates_exclude_restaurants(self):
        base = {'mapx': '126.977', 'mapy': '37.575', 'title': '광화문'}
        catalog = {'1': dict(base, contenttypeid='12'), '2': dict(base, contenttypeid='39')}
        self.assertEqual(tour.candidate_ids('광화문', catalog), ['1'])

    def test_statue_alias(self):
        item = {'mapx': '126.977', 'mapy': '37.575', 'title': '충무공 이순신 동상', 'contenttypeid': '12'}
        self.assertEqual(tour.candidate_ids('이순신장군동상', {'1': item}), ['1'])

    def test_selection_deduplicates_and_distinguishes_palace(self):
        base = {'mapx': '126.977', 'mapy': '37.575', 'contenttypeid': '12'}
        catalog = {'rental': dict(base, title='한복남 경복궁점'), 'palace': dict(base, title='경복궁')}
        for i in range(15):
            catalog[str(i)] = dict(base, title=f'주변 장소 {i}')
        ids, landmarks = tour.select_ids(catalog)
        self.assertEqual(ids[0], 'palace')
        self.assertEqual(len(ids), 11)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(landmarks), 8)

    @patch('collect_tourapi.time.sleep')
    def test_encoded_key_success_and_redaction(self, sleep):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'raw').mkdir()
            client = tour.Client('TEST%2BKEY%2F%3D', root)
            response = {'response': {'header': {'resultCode': '0000'}, 'body': {'items': {'item': [{'overview': 'TEST+KEY/='}]}, 'totalCount': 1}}}
            completed = subprocess.CompletedProcess([], 0, json.dumps(response) + '\n200', '')
            with patch('collect_tourapi.subprocess.run', return_value=completed) as run:
                _, items = client.get('detailCommon2', contentId='1')
            config = run.call_args.kwargs['input']
            self.assertIn('serviceKey=TEST%2BKEY%2F%3D', config)
            self.assertNotIn('serviceKey', ' '.join(run.call_args.args[0]))
            self.assertEqual(items[0]['overview'], '[REDACTED]')
            for path in root.rglob('*'):
                if path.is_file():
                    self.assertNotIn('TEST', path.read_text())

    @patch('collect_tourapi.time.sleep')
    def test_auth_error_stops_without_retry(self, sleep):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'raw').mkdir()
            client = tour.Client('test-secret', root)
            response = {'OpenAPI_ServiceResponse': {'cmmMsgHeader': {'returnReasonCode': '30'}}}
            with patch('collect_tourapi.subprocess.run', return_value=subprocess.CompletedProcess([], 0, json.dumps(response) + '\n403', '')) as run:
                with self.assertRaises(tour.StopCollection):
                    client.get('locationBasedList2')
            self.assertEqual(run.call_count, 1)

    @patch('collect_tourapi.Client.get')
    def test_pagination(self, get):
        get.side_effect = [({'totalCount': 101}, [{'contentid': str(i)} for i in range(100)]),
                           ({'totalCount': 101}, [{'contentid': '100'}])]
        client = tour.Client('test-secret', Path('/unused'))
        self.assertEqual(len(client.pages('locationBasedList2')), 101)
        self.assertEqual(get.call_args.kwargs['pageNo'], 2)


if __name__ == '__main__':
    unittest.main()

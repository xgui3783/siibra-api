import json

from fastapi.testclient import TestClient

from app.app import app

client = TestClient(app)

ICBM_152_SPACE_ID='minds/core/referencespace/v1.0.0/dafcffc5-4826-4bf1-8ff6-46b8a31ff8e2'
ATLAS_ID = 'juelich/iav/atlas/v1.0.0/1'
PARCELLATION_ID = 'minds%2Fcore%2Fparcellationatlas%2Fv1.0.0%2F94c1125b-b87e-45e4-901c-00daee7f2579-25'
INVALID_PARCELLATION_ID = 'INVALID_PARCELLATION_ID'
REGION_NAME = 'Ch 123 (Basal Forebrain) - left hemisphere'
REGION_ID = 'minds%2Fcore%2Fparcellationregion%2Fv1.0.0%2Fbb111a95-e04c-4987-8254-4af4ed8b0022'
HOC1_REGION_ID = 'minds%2Fcore%2Fparcellationregion%2Fv1.0.0%2F5151ab8f-d8cb-4e67-a449-afe2a41fb007'
INVALID_REGION_NAME = 'INVALID_REGION'
SPACE_ID = 'minds%2Fcore%2Freferencespace%2Fv1.0.0%2Fdafcffc5-4826-4bf1-8ff6-46b8a31ff8e2'
VALID_MODALITY='EbrainsRegionalDataset'
VALID_MODALITY_INSTANCE_ID='https%3A%2F%2Fnexus.humanbrainproject.org%2Fv0%2Fdata%2Fminds%2Fcore%2Fdataset%2Fv1.0.0%2F87c6dea7-bdf7-4049-9975-6a9925df393f'

def test_get_all_parcellations():
    response = client.get(
        '/v1_0/atlases/{}/parcellations'.format(ATLAS_ID.replace('/', '%2F')),
        headers={"Authorization": "Bearer token"}
    )
    result_content = json.loads(response.content)
    assert response.status_code == 200
    assert len(result_content) > 0


def test_get_one_parcellation_by_id():
    response = client.get('/v1_0/atlases/{}/parcellations/{}'.format(ATLAS_ID.replace('/', '%2F'), PARCELLATION_ID))
    url = response.url.split('atlases')[0]
    result_content = json.loads(response.content)
    assert response.status_code == 200
    assert result_content['id'] == {
        'kg': {
            'kgSchema': 'minds/core/parcellationatlas/v1.0.0',
            'kgId': '94c1125b-b87e-45e4-901c-00daee7f2579-25'
        }
    }
    assert result_content['name'] == 'Julich-Brain Cytoarchitectonic Maps 2.5'
    assert result_content['version'] == {
        'name': '2.5',
        'next': 'minds/core/parcellationatlas/v1.0.0/94c1125b-b87e-45e4-901c-00daee7f2579-273',
        'prev': 'minds/core/parcellationatlas/v1.0.0/94c1125b-b87e-45e4-901c-00daee7f2579'
    }


def test_all_regions_for_parcellations():
    response = client.get('/v1_0/atlases/{}/parcellations/{}/regions?space_id={}'.format(
        ATLAS_ID.replace('/', '%2F'),
        PARCELLATION_ID,
        ICBM_152_SPACE_ID))
    result_content = json.loads(response.content)
    assert response.status_code == 200
    assert len(result_content) == 2
    assert result_content[0]['children'] is not None


def test_all_regions_for_parcellations_with_bad_request():
    response = client.get('/v1_0/atlases/{}/parcellations/{}/regions'.format(ATLAS_ID.replace('/', '%2F'), INVALID_PARCELLATION_ID))
    assert response.status_code == 400
    result_content = json.loads(response.content)
    assert result_content['detail'] == 'The requested parcellation is not supported by the selected atlas.'


def test_get_one_region_for_parcellation_without_extra_data():
    response = client.get('/v1_0/atlases/{}/parcellations/{}/regions/{}'.format(ATLAS_ID.replace('/', '%2F'), PARCELLATION_ID, REGION_ID))
    result_content = json.loads(response.content)
    assert response.status_code == 200

    # siibra-python v0.1a4 sanitize region name
    import re
    REMOVE_FROM_NAME=['hemisphere','-']

    def _clear_name(name):
        for word in REMOVE_FROM_NAME:
            name = re.sub(r' *'+word,'',name)
        return name

    assert result_content['name'] == _clear_name(REGION_NAME)
    assert result_content['availableIn'] is not None


def test_get_one_region_for_parcellation_with_extra_data():
    response = client.get('/v1_0/atlases/{}/parcellations/{}/regions/{}?space_id={}'.format(ATLAS_ID.replace('/', '%2F'), PARCELLATION_ID, REGION_ID, SPACE_ID))
    result_content = json.loads(response.content)
    assert response.status_code == 200

    # siibra-python v0.1a4 sanitize region name
    import re
    REMOVE_FROM_NAME=['hemisphere','-']

    def _clear_name(name):
        for word in REMOVE_FROM_NAME:
            name = re.sub(r' *'+word,'',name)
        return name

    assert result_content['name'] == _clear_name(REGION_NAME)
    # Add Assertion for extra data


def test_get_region_for_space_with_invalid_region_name():
    pass
    # response = client.get('/atlases/{}/spaces/{}/regions/{}'.format(ATLAS_ID.replace('/', '%2F'), SPACE_ID, INVALID_REGION_NAME))
    # result_content = json.loads(response.content)
    # assert response.status_code == 404
    # assert result_content['detail'] == 'region with name: {} not found'.format(INVALID_REGION_NAME)

def test_regional_modality_by_id():
    url='/v1_0/atlases/{}/parcellations/{}/regions/{}/features/{}/{}'.format(
        ATLAS_ID.replace('/', '%2F'), PARCELLATION_ID, HOC1_REGION_ID, VALID_MODALITY, VALID_MODALITY_INSTANCE_ID)
    print('url', url)
    response = client.get(url)
    
    result_content = json.loads(response.content)
    assert response.status_code == 200

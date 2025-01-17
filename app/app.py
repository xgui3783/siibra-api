# Copyright 2018-2020 Institute of Neuroscience and Medicine (INM-1),
# Forschungszentrum Jülich GmbH

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import requests
import json
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from siibra.ebrains import Authentication
from fastapi_versioning import VersionedFastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .siibra_api import router as siibra_router
from .atlas_api import router as atlas_router
from .space_api import router as space_router
from .health import router as health_router
from .parcellation_api import router as parcellation_router, preheat, get_preheat_status
from .ebrains_token import get_public_token
from .siibra_custom_exception import SiibraCustomException
from . import logger


security = HTTPBearer()

# Tags to structure the api documentation
tags_metadata = [
    {
        "name": "atlases",
        "description": "Atlas related data",
    },
    {
        "name": "parcellations",
        "description": "Parcellations related data, depending on selected atlas",
    },
    {
        "name": "spaces",
        "description": "Spaces related data, depending on selected atlas",
    },
    {
        "name": "data",
        "description": "Further information like, genes, features, ...",
    },
]

# Main fastAPI application
app = FastAPI(
    title="Siibra API",
    description="This is the REST api for siibra tools",
    version="1.0",
    openapi_tags=tags_metadata
)
# Add a siibra router with further endpoints
app.include_router(parcellation_router)
app.include_router(space_router)
app.include_router(atlas_router)
app.include_router(siibra_router)
app.include_router(health_router)


# Versioning for all api endpoints
app = VersionedFastAPI(app, default_api_version=1)

# Template list, with every template in the project
# can be rendered and returned
templates = Jinja2Templates(directory='templates/')
app.mount("/static", StaticFiles(directory="static"), name="static")

pypi_stat_url = 'https://pypistats.org/api/packages/siibra/overall?mirrors=false'

# Allow CORS
origins = ['*']
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=['GET'],
)


@app.get('/', include_in_schema=False)
def home(request: Request):
    """
    Return the template for the siibra landing page.

    :param request: fastApi Request object
    :return: the rendered index.html template
    """
    return templates.TemplateResponse(
        'index.html', context={
            'request': request})


@app.get('/stats', include_in_schema=False)
def home(request: Request):
    """
    Return the template for the siibra statistics.

    :param request: fastApi Request object
    :return: the rendered stats.html template
    """
    download_data_json = requests.get(pypi_stat_url)
    if download_data_json.status_code == 200:
        download_data = json.loads(download_data_json.content)

        download_sum = 0
        download_sum_month = {}

        for d in download_data['data']:
            download_sum += d['downloads']
            date_index = '{}-{}'.format(d['date'].split('-')
                                        [0], d['date'].split('-')[1])
            if date_index not in download_sum_month:
                download_sum_month[date_index] = 0
            download_sum_month[date_index] += d['downloads']

        return templates.TemplateResponse('stats.html', context={
            'request': request,
            'download_sum': download_sum,
            'download_sum_month': download_sum_month
        })
    else:
        logger.warn('Could not retrieve pypi statistics')
        raise HTTPException(status_code=500,
                            detail='Could not retrieve pypi statistics')


@app.middleware('http')
async def set_auth_header(request: Request, call_next):
    """
    Set authentication for further requests with siibra
    If a user provides a header, this one will be used otherwise use the default public token
    :param request: current request
    :param call_next: next middleware function
    :return: an altered response
    """
    auth = Authentication.instance()
    bearer_token = request.headers.get('Authorization')
    try:
        if bearer_token:
            auth.set_token(bearer_token.replace('Bearer ', ''))
        else:
            public_token = get_public_token()
            auth.set_token(public_token)
        response = await call_next(request)
        return response
    except SiibraCustomException as err:
        logger.error('Could not set authentication token')
        return JSONResponse(
            status_code=err.status_code, content={
                'message': err.message})


@app.middleware('http')
async def matomo_request_log(request: Request, call_next):
    """
    Middleware will be executed before each request.
    If the URL does not belog to a resource file, a log will be send to matomo monitoring.
    :param request: current fastAPI request object
    :param call_next: next middleware method
    :return: the response after preprocessing
    """
    test_url = request.url
    test_list = ['.css', '.js', '.png', '.gif', '.json', '.ico']
    res = any(ele in str(test_url) for ele in test_list)

    if 'SIIBRA_ENVIRONMENT' in os.environ:
        if os.environ['SIIBRA_ENVIRONMENT'] == 'PRODUCTION':
            if not res:
                payload = {
                    'idsite': 13,
                    'rec': 1,
                    'action_name': 'siibra_api',
                    'url': request.url,
                    '_id': 'my_ip',
                    'lang': request.headers.get('Accept-Language'),
                    'ua': request.headers.get('User-Agent')
                }
                try:
                    # r = requests.get('https://stats.humanbrainproject.eu/matomo.php', params=payload)
                    # print('Matomo logging with status: {}'.format(r.status_code))
                    pass
                except Exception:
                    logger.info('Could not log to matomo instance')
        else:
            logger.info('Request for: {}'.format(request.url))
    response = await call_next(request)
    return response

@app.get('/ready', include_in_schema=False)
def get_ready():
    if not all([get_preheat_status()]):
        raise HTTPException(400, detail='Not yet ready.')
    return 'OK'

@app.on_event('startup')
async def on_startup():
    import asyncio
    from signal import SIGINT, SIGTERM

    async def run_async():
        loop=asyncio.get_event_loop()

        # TODO still doesn't work quite right, but ... hopefully getting closer?
        def cleanup_on_termination():
            logger.info(f'Terminating... Cancelling pending tasks...')
            
            loop.stop()
            loop.close()

        def run_preheat():
            preheat()
            pass

        for sig in [SIGINT, SIGTERM]:
            loop.add_signal_handler(sig, cleanup_on_termination)
        
        loop.run_in_executor(None, run_preheat)

    asyncio.ensure_future(run_async())

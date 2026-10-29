import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from sim.driver import RunResult
from sim.runner import execute_script
from sim_plugin_lumerical import LumericalFDTDDriver, LumericalRCWADriver


@pytest.fixture
def backend():
    requests = []
    def reply(request):
        payload = json.loads(request.content or b'{}')
        requests.append((request.url.host, request.url.path, payload, request.headers.get('X-Sim-Session')))
        if request.url.path == '/health':
            return httpx.Response(200, json={'ok': True, 'data': {'status': 'healthy', 'active_sessions': 0}})
        if request.url.path.startswith('/detect/'):
            return httpx.Response(200, json={'ok': True, 'data': {'installs': [{'name': request.url.path.rsplit('/',1)[1], 'version': 'test', 'path': 'fixture', 'extra': {}}]}})
        if request.url.path == '/connect':
            if payload.get('solver') not in ('lumerical-fdtd', 'lumerical-rcwa'):
                return httpx.Response(400, json={'detail': 'missing solver'})
            return httpx.Response(200, json={'ok': True, 'data': {'session_id': 's-backend', 'solver': payload['solver'], 'run_count': 0, 'launch_options': {}}})
        if request.url.path in ('/exec', '/disconnect'):
            if request.headers.get('X-Sim-Session') != 's-backend':
                return httpx.Response(400, json={'detail': 'missing session selector'})
            return httpx.Response(200, json={'ok': True, 'data': {'stdout': 'done', 'stderr': '', 'disconnected': request.url.path=='/disconnect'}})
        if request.url.path == '/run':
            if 'script' not in payload:
                return httpx.Response(422, json={'detail': 'script is required'})
            return httpx.Response(200, json={'ok': True, 'data': {'exit_code': 0, 'stdout': 'done', 'stderr': '', 'errors': [], 'artifacts': [{'path': 'result.csv'}]}})
        return httpx.Response(404)
    return httpx.MockTransport(reply), requests


def controlled(cls, backend, host='solver.test'):
    driver = cls(host=host)
    driver.client._client = httpx.Client(transport=backend[0])
    return driver


@pytest.mark.parametrize('cls', [LumericalFDTDDriver, LumericalRCWADriver])
def test_core_session_uses_launch_and_owns_backend_session(cls, backend, monkeypatch):
    from sim import drivers, server
    driver = controlled(cls, backend)
    assert callable(getattr(driver, 'launch', None)), 'missing core launch contract'
    monkeypatch.setattr(drivers, 'get_driver', lambda name: driver)
    with TestClient(server.app) as api:
        opened = api.post('/connect', json={'solver': driver.name, 'ui_mode': 'no_gui'})
        assert opened.status_code == 200, opened.text
        sid = opened.json()['data']['session_id']
        assert sid == 's-backend'
        headers = {'X-Sim-Session': sid}
        result = api.post('/exec', headers=headers, json={'code': 'x=1;', 'label': 'probe'})
        assert result.json()['ok'] is True
        assert result.json()['data']['stdout'] == 'done'
        assert api.post('/disconnect', headers=headers).json()['ok'] is True
    connect = next(row for row in backend[1] if row[1]=='/connect')
    assert connect[2]['solver'] == driver.name
    assert driver._session_id is None


def test_missing_host_fails_without_a_network_probe(monkeypatch):
    monkeypatch.delenv('LUMERICAL_HOST', raising=False)
    driver = LumericalFDTDDriver()
    assert callable(getattr(driver, 'launch', None))
    result = driver.launch()
    assert result['ok'] is False
    assert result['error_code'] == 'RUN_FAILED'
    assert 'host' in result['message'].lower()


@pytest.mark.parametrize('cls',[LumericalFDTDDriver,LumericalRCWADriver])
def test_one_shot_preserves_core_result_contract(cls,backend,tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    script = tmp_path/'input.lsf';script.write_text('x=1;')
    driver = controlled(cls,backend)
    result = execute_script(script,solver=driver.name,driver=driver)
    assert isinstance(result,RunResult)
    assert result.ok and result.stdout=='done'
    assert result.artifacts==[{'path':'result.csv'}]
    assert result.workspace_delta==[]
    request=next(r for r in backend[1] if r[1]=='/run')
    assert request[2]=={'script':str(script),'solver':driver.name}


@pytest.mark.parametrize('response',[
    {'ok':False,'error':'license unavailable'},
    {'ok':True,'data':{'exit_code':0,'errors':['solve failed']}},
    {'ok':False,'data':{'exit_code':0,'stderr':'failed'}},
])
def test_one_shot_cannot_mask_remote_failure(response,tmp_path):
    driver=LumericalFDTDDriver(host='solver.test')
    driver.client._client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json=response)))
    script=tmp_path/'input.lsf';script.write_text('x=1;')
    result=driver.run_file(script)
    assert isinstance(result,RunResult)
    assert result.exit_code!=0 and not result.ok


def test_json_request_uses_explicit_remote_script(backend,tmp_path):
    driver=controlled(LumericalRCWADriver,backend)
    request=tmp_path/'run.json';request.write_text(json.dumps({'script':'C:/shared/test.lsf'}))
    assert driver.run_file(request).ok
    assert backend[1][-1][2]=={'script':'C:/shared/test.lsf','solver':'lumerical-rcwa'}


def test_idle_disconnect_does_not_close_someone_elses_session(backend):
    driver=controlled(LumericalFDTDDriver,backend)
    assert driver.disconnect()['ok'] is True
    assert backend[1]==[]


def test_remote_api_wrapper_requires_an_explicit_host(monkeypatch):
    from sim_plugin_lumerical.remote_lumapi import RemoteLumapi
    monkeypatch.delenv('LUMERICAL_HOST',raising=False)
    with pytest.raises(ValueError,match='host'):
        RemoteLumapi()


def test_two_backend_targets_stay_separate(backend):
    for cls,host in [(LumericalFDTDDriver,'first.test'),(LumericalRCWADriver,'second.test')]:
        driver=controlled(cls,backend,host=host)
        assert driver.launch()['ok']
        assert driver.run('x=1;')['ok']
        assert driver.disconnect()['ok']
    assert {row[0] for row in backend[1]}=={'first.test','second.test'}


def test_one_shot_rejects_success_without_run_result(tmp_path):
    driver=LumericalFDTDDriver(host='solver.test')
    driver.client._client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'ok':True})))
    script=tmp_path/'input.lsf';script.write_text('x=1;')
    assert not driver.run_file(script).ok

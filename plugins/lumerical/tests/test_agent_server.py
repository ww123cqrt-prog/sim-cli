import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace


def test_headless_connection_honors_no_gui(monkeypatch):
    file=Path(__file__).resolve().parents[1]/'lumerical_agent_server.py'
    spec=importlib.util.spec_from_file_location('lumerical_backend_test',file)
    server=importlib.util.module_from_spec(spec);sys.modules[spec.name]=server;spec.loader.exec_module(server)
    options=[]
    class Session:
        def __init__(self,**kwargs):options.append(kwargs)
        def close(self):pass
    monkeypatch.setattr(server,'_import_lumapi',lambda:SimpleNamespace(FDTD=Session))
    result=server.connect(server.ConnectRequest(ui_mode='no_gui'))
    try:
        assert options==[{'hide':True}]
    finally:
        server._sessions.clear()

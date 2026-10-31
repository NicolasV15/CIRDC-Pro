import asyncio
import json
from cirdc.cli import main
from cirdc.mcp_server import server


def test_mcp_exposes_the_metadata_contract():
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == {'doctor', 'plan_update', 'start_update', 'run_status',
                                      'resume_update', 'retry_update', 'get_paper', 'analyze_relations',
                                      'author_init', 'author_fetch', 'author_import', 'author_update', 'author_show'}
    assert all(t.description and t.inputSchema and t.outputSchema for t in tools)


def test_cli_failure_is_structured_without_connection_secrets(tmp_path, capsys):
    cfg = tmp_path / 'config.json'
    cfg.write_text(json.dumps({'data_root': str(tmp_path), 'mysql': {'host': '127.0.0.1', 'port': 1,
                                                                 'user': 'fixture', 'password': 'never-print-this'}}))
    code = main(['--config', str(cfg), 'status', '--json'])
    output = capsys.readouterr().out
    assert code == 1
    assert 'never-print-this' not in output
    data = json.loads(output)
    assert data['schema_version'] == 1 and data['status'] == 'error'

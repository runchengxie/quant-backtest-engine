"""Stage immutable exporters in their historical layout outside the checkout."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.workspace import source_path


def stage_sources(root:Path,stage:Path)->None:
    root=root.resolve();stage=stage.resolve()
    if stage==root or stage.is_relative_to(root):raise ValueError('stage must be outside source')
    fixture=json.loads((root/'docs/assets/method/fixtures.json').read_text())
    sources=fixture['exporter_sources']|{'project_tools/export_method_fixtures.py':fixture['exporter_sha256']}
    opportunity=json.loads((root/'docs/assets/learning/opportunity.json').read_text())['provenance']['exporter']
    sources[opportunity['path']]=opportunity['sha256']
    stage.mkdir(parents=True,exist_ok=False)
    for name,digest in sources.items():
        if not name.startswith('project_tools/') or '..' in Path(name).parts:raise ValueError('invalid legacy exporter source')
        original=source_path(root,name)
        if hashlib.sha256(original.read_bytes()).hexdigest()!=digest:raise ValueError('exporter differs from historical bytes')
        destination=stage/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,destination)
    for old,current in [('fixtures/roundtrip.json','tests/fixtures/roundtrip.json'),('docs/assets/method/owner-lock.json','docs/assets/method/owner-lock.json')]:
        destination=stage/old;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/current,destination)


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--engine',type=Path);parser.add_argument('--kind',choices=['method','opportunity'],default='method');parser.add_argument('--output',type=Path,required=True);parser.add_argument('--receipt',type=Path);args=parser.parse_args()
    output=args.output.resolve()
    if output.is_relative_to(ROOT) or output.exists():raise ValueError('fresh external output required')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='method-owner-stage-',dir=output.parent) as directory:
        stage=Path(directory)/'legacy';stage_sources(ROOT,stage)
        script='export_method_fixtures.py' if args.kind=='method' else 'export_opportunity_example.py'
        command=[sys.executable,str(stage/'project_tools'/script),'--output',str(output)]
        if args.kind=='method':
            if args.engine is None:raise ValueError('method reproduction requires registered engine')
            command+=['--engine',str(args.engine.resolve())]
        if args.receipt is not None:
            receipt=args.receipt.resolve()
            if receipt.is_relative_to(ROOT) or receipt.exists():raise ValueError('fresh external receipt required')
            command+=['--receipt',str(receipt)]
        subprocess.run(command,check=True,cwd=stage)

if __name__=='__main__':main()

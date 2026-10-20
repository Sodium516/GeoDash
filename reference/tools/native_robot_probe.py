"""Read-only airborne Robot velocity probe with no ground-jump latch.

All native physics helpers execute, with the velocity probe's minimal state.
These cases check that held input alone cannot suspend a Robot's fall.
"""
import argparse
import itertools
import json
from native_velocity_probe import Probe,HASH


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary');parser.add_argument('--output',required=True)
    args=parser.parse_args();probe=Probe(args.binary);rows=[]
    for mini,upside,held,vy in itertools.product((False,True),(False,True),(False,True),(-5,0,5)):
        row=dict(mini=mini,upside=upside,held=held,vy=vy)
        try:row['native_vy']=probe.step(mode='robot',**row)
        except Exception as error:row['unsupported']=str(error)
        rows.append(row)
    with open(args.output,'w') as output:
        json.dump(dict(binary_sha256=HASH,method='updateJump airborne robot',limitation=__doc__,cases=rows),output,indent=2)
        output.write('\n')
    print('Recorded',sum('native_vy' in row for row in rows),'of',len(rows),'Robot samples')


if __name__=='__main__':main()

"""Fresh UFO flap velocity microprobe. Burst visual effect is skipped.

Uses the hash-guarded installed binary; no game files or saves are modified.
Only the graphical playBurstEffect helper is skipped; velocity helpers execute.
This does not establish complete input scheduling or collision parity.
"""
import argparse
import json
import struct
from native_velocity_probe import Probe,PLAYER,STOP,ENTRY,HASH
class Flap(Probe):
 def hook(self,mu,pc,size,data):
  ins=struct.unpack('<I',mu.mem_read(pc,4))[0]
  if ins&0xfc000000==0x94000000:
   imm=ins&0x3ffffff
   if imm&0x2000000:imm-=0x4000000
   if pc+imm*4==0x10037bb60:
    mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
  super().hook(mu,pc,size,data)


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('binary');parser.add_argument('--output',required=True)
 args=parser.parse_args();probe=Flap(args.binary);rows=[]
 for mini in (False,True):
  for upside in (False,True):
   for vy in (-5,0,5,9):
    row=dict(mini=mini,upside=upside,vy=vy)
    probe.prepare(mode='ufo',held=True,**row)
    probe.mu.mem_write(PLAYER+0x936,b'\x01')
    try:
     probe.mu.emu_start(ENTRY,STOP,count=100000)
     if probe.mu.reg_read(probe.regs.UC_ARM64_REG_PC)!=STOP:raise RuntimeError('Instruction limit')
     row['native_vy']=struct.unpack('<d',probe.mu.mem_read(PLAYER+0x950,8))[0]
    except Exception as error:row['unsupported']=str(error)
    rows.append(row)
 with open(args.output,'w') as output:
  json.dump(dict(binary_sha256=HASH,method='updateJump, held and stateRingJump',dt=.225,
   limitation='Velocity only; graphical burst skipped; no slopes, collisions or full input pipeline',cases=rows),output,indent=2)
  output.write('\n')
 print('Recorded',sum('native_vy' in row for row in rows),'of',len(rows),'flap samples')


if __name__=='__main__':main()

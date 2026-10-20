"""Grounded cube/ball impulse probe against the hash-guarded installed binary.

Clock, jump statistics and rotation effects are skipped. flipGravity's physics
prefix executes, then its visual/contact cleanup tail is skipped. Velocity-only
free-standing ground actions; not slope, collision or full-game evidence.
"""
import argparse
import json
import struct
from native_velocity_probe import Probe,PLAYER,STOP,ENTRY,HASH
class Flap(Probe):
 def hook(self,mu,pc,size,data):
  if pc==0x10037b578:
   mu.reg_write(self.regs.UC_ARM64_REG_PC,0x10037b754);return
  ins=struct.unpack('<I',mu.mem_read(pc,4))[0]
  if ins&0xfc000000==0x94000000:
   imm=ins&0x3ffffff
   if imm&0x2000000:imm-=0x4000000
   if pc+imm*4 in (0x10037bb60,0x10038b330,0x10037ac1c,0x10037b3d0,0x10037a398):
    mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
  super().hook(mu,pc,size,data)






def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('binary');parser.add_argument('--output',required=True)
 args=parser.parse_args();probe=Flap(args.binary)
 probe.helpers.update({0x10037b40c,0x10029cf24})
 rows=[]
 for mode in ('cube','ball'):
  for mini in (False,True):
   for upside in (False,True):
    row=dict(mode=mode,mini=mini,upside=upside)
    probe.prepare(vy=0,held=True,**row)
    for off in (0x5a8,0x5b0,0x5b8,0x5c0):probe.mu.mem_write(PLAYER+off,struct.pack('<Q',PLAYER+0x7000))
    probe.mu.mem_write(PLAYER+0x936,b'\x01');probe.mu.mem_write(PLAYER+0x971,b'\x01')
    try:
     probe.mu.emu_start(ENTRY,STOP,count=100000)
     if probe.mu.reg_read(probe.regs.UC_ARM64_REG_PC)!=STOP:raise RuntimeError('Instruction limit')
     row['native_vy']=struct.unpack('<d',probe.mu.mem_read(PLAYER+0x950,8))[0]
    except Exception as error:row['unsupported']=str(error)
    rows.append(row)
 with open(args.output,'w') as output:
  json.dump(dict(binary_sha256=HASH,method='updateJump grounded cube and ball',limitation=__doc__,cases=rows),output,indent=2)
  output.write('\n')
 print('Recorded',sum('native_vy' in row for row in rows),'of',len(rows),'ground impulses')


if __name__=='__main__':main()

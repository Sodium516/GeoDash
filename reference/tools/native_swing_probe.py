"""Swing flip velocity probe using read-only installed engine code.

Skips native 0x37b578..0x37b5fc (artwork, scale, streak effects) and updateSwingFire.
Runs flipGravity's gravity/velocity state changes and updateJump arithmetic.
Synthetic empty collision logs. Numerical samples are not full engine parity.
"""
import argparse
import json
import struct
from native_velocity_probe import Probe,PLAYER,STOP,ENTRY,HASH
class Flap(Probe):
 def hook(self,mu,pc,size,data):
  if pc==0x10037b578:
   mu.reg_write(self.regs.UC_ARM64_REG_PC,0x10037b5fc);return
  ins=struct.unpack('<I',mu.mem_read(pc,4))[0]
  if ins&0xfc000000==0x94000000:
   imm=ins&0x3ffffff
   if imm&0x2000000:imm-=0x4000000
   if pc+imm*4 in (0x10037bb60,0x10038b330):
    mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
  super().hook(mu,pc,size,data)




def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('binary');parser.add_argument('--output',required=True)
 args=parser.parse_args();probe=Flap(args.binary)
 probe.helpers.update({0x10037b40c,0x10029cf24,0x10022d91c})
 rows=[]
 for mini in (False,True):
  for upside in (False,True):
   for vy in (-5,0,5,9):
    row=dict(mini=mini,upside=upside,vy=vy)
    probe.prepare(mode='swing',held=True,**row)
    for off in (0x5a8,0x5b0,0x5b8,0x5c0):probe.mu.mem_write(PLAYER+off,struct.pack('<Q',PLAYER+0x7000))
    probe.mu.mem_write(PLAYER+0x936,b'\x01')
    try:
     probe.mu.emu_start(ENTRY,STOP,count=100000)
     if probe.mu.reg_read(probe.regs.UC_ARM64_REG_PC)!=STOP:raise RuntimeError('Instruction limit')
     row['native_vy']=struct.unpack('<d',probe.mu.mem_read(PLAYER+0x950,8))[0]
     row['native_upside']=bool(probe.mu.mem_read(PLAYER+0x96f,1)[0])
    except Exception as error:row['unsupported']=str(error)
    rows.append(row)
 with open(args.output,'w') as output:
  json.dump(dict(binary_sha256=HASH,method='updateJump Swing fresh flip',limitation=__doc__,cases=rows),output,indent=2)
  output.write('\n')
 print('Recorded',sum('native_vy' in row for row in rows),'of',len(rows),'Swing samples')


if __name__=='__main__':main()

"""Native ramp-assisted ground-jump microprobe.

Uses the exclusions in native_ground_probe: clock/statistics and visual cleanup.
Executes getModifiedSlopeYVel and native velocity setters with supplied ramp
velocity/ride age. Does not prove the recreation's collision-derived ramp state. --robot stops
after the completed impulse write at0x377d90, before sprite animation.
"""
import argparse
import itertools
import json
import struct
from native_ground_probe import Flap as GroundProbe
from native_velocity_probe import PLAYER,STOP,ENTRY,HASH

class Flap(GroundProbe):
 def hook(self,mu,pc,size,data):
  # Robot's impulse is complete here; stop before its sprite animation branch.
  if pc==0x100377d90 and mu.mem_read(PLAYER+0x96d,1)[0]:
   mu.reg_write(self.regs.UC_ARM64_REG_PC,STOP);return
  super().hook(mu,pc,size,data)


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('binary');parser.add_argument('--output',required=True)
 parser.add_argument('--robot',action='store_true',help='Probe Robot launch through the completed impulse write, before sprite work')
 args=parser.parse_args();probe=Flap(args.binary)
 probe.helpers.update({0x10037b40c,0x10029cf24,0x10037b378})
 rows=[]
 for mode,mini,upside,age,slope in itertools.product(('robot',) if args.robot else ('cube','ball'),(False,True),(False,True),(.02,.06,.2),(0,8,16,100)):
  row=dict(mode=mode,mini=mini,upside=upside,age=age,slope=slope)
  probe.prepare(mode=mode,mini=mini,upside=upside,vy=0,held=True)
  for off in (0x5a8,0x5b0,0x5b8,0x5c0):probe.mu.mem_write(PLAYER+off,struct.pack('<Q',PLAYER+0x7000))
  for off in (0x936,0x971,0x960):probe.mu.mem_write(PLAYER+off,b'\x01')
  probe.mu.mem_write(PLAYER+0x964,struct.pack('<f',-slope if upside else slope))
  probe.mu.mem_write(PLAYER+0xa38,struct.pack('<d',age))
  try:
   probe.mu.emu_start(ENTRY,STOP,count=100000)
   if probe.mu.reg_read(probe.regs.UC_ARM64_REG_PC)!=STOP:raise RuntimeError('Instruction limit')
   row['native_vy']=struct.unpack('<d',probe.mu.mem_read(PLAYER+0x950,8))[0]
  except Exception as error:row['unsupported']=str(error)
  rows.append(row)
 with open(args.output,'w') as output:
  json.dump(dict(binary_sha256=HASH,method='updateJump ramp-assisted ground jump',limitation=__doc__,cases=rows),output,indent=2)
  output.write('\n')
 print('Recorded',sum('native_vy' in row for row in rows),'of',len(rows),'ramp jump samples')


if __name__=='__main__':main()

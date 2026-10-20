"""Read-only native position-integration slice, after velocity calculation.

Runs 0x375c6c through the position setter, then stops before rendering and effects.
Synthetic position accessors only; no contacts, portals or level input scheduling.
"""
import argparse
import json
import struct
from native_contact_probe import Contact
from native_velocity_probe import PLAYER,STOP,HASH
class Position(Contact):
 def hook(self,mu,pc,size,data):
  super().hook(mu,pc,size,data)
  if pc==0x100375df8:mu.emu_stop()
 def step_position(self,x,y,vy):
  self.prepare(mode='cube',vy=vy)
  mu=self.mu;r=self.regs
  mu.mem_write(PLAYER,struct.pack('<Q',PLAYER+0x4000))
  for off in range(0,0x1000,8):mu.mem_write(PLAYER+0x4000+off,struct.pack('<Q',STOP+off))
  mu.mem_write(PLAYER+0x8100,struct.pack('<ff',x,y))
  mu.reg_write(r.UC_ARM64_REG_X19,PLAYER)
  mu.reg_write(r.UC_ARM64_REG_S8,struct.unpack('<I',struct.pack('<f',.25))[0])
  mu.reg_write(r.UC_ARM64_REG_S9,struct.unpack('<I',struct.pack('<f',.225))[0])
  mu.emu_start(0x100375c6c,STOP,count=100000)
  return struct.unpack('<ff',mu.mem_read(PLAYER+0x8100,8))


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('binary');parser.add_argument('--output',required=True)
 args=parser.parse_args();probe=Position(args.binary);rows=[]
 for x in (0,1000,10000,25640.9609375):
  for y,vy in ((69.22732543945312,-.912),(150,6.871),(123.456,11.18),(1,-4.444)):
   row=dict(x=x,y=y,vy=vy)
   try:row['native_position']=probe.step_position(**row)
   except Exception as error:row['unsupported']=str(error)
   rows.append(row)
 with open(args.output,'w') as output:
  json.dump(dict(binary_sha256=HASH,method='PlayerObject::update position integration slice',limitation=__doc__,cases=rows),output,indent=2)
  output.write('\n')
 print('Recorded',sum('native_position' in row for row in rows),'of',len(rows),'position samples')


if __name__=='__main__':main()
